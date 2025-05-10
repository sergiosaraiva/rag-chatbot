import os
import uuid
import structlog
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from openai import OpenAI
from dotenv import load_dotenv

from sqlalchemy.orm import Session
from fastapi import Depends
import json
from datetime import datetime
from app.database import get_db, Conversation, Message

from app.models import ChatRequest, ChatResponse
from app.chunk_and_index import index_file, get_chroma_client, get_embeddings

import logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.5"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "256"))
TOP_P = float(os.getenv("TOP_P", "0.7"))
FREQUENCY_PENALTY = float(os.getenv("FREQUENCY_PENALTY", "0.0"))
PRESENCE_PENALTY = float(os.getenv("PRESENCE_PENALTY", "0.0"))
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "text-embedding-3-small")
RESPONSE_PREFIX = os.getenv("RESPONSE_PREFIX", "")

# Chroma configuration
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "kb_default")
TOP_K = int(os.getenv("TOP_K", "5"))

# System prompt template
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", 
                         "You are an expert assistant. Use the following context to answer:\n\n{context}\n\nAnswer conversationally. If you don't know the answer based on the provided context, say so.")

# Context memory - how many turns to remember
CONTEXT_MEMORY = int(os.getenv("CONTEXT_MEMORY", "20"))

# Configure OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# In-memory session history - includes messages and retrieved context
#session_history: Dict[str, Dict[str, Any]] = {}

port = int(os.getenv("PORT", 8000))
print(f"Starting on port: {port}")

# Initialize FastAPI
app = FastAPI(
    title="RAG Chatbot API",
    description="A backend service for RAG-based chatbot",
    version="1.0.0"
)

# Add rate limiting exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure kb_files directory exists
os.makedirs("kb_files", exist_ok=True)


@app.get("/")
@limiter.limit("10/minute")
async def root(request: Request):
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/api/test/chromadb")
def test_chromadb():
    import requests
    chroma_url = os.getenv("CHROMA_SERVER_URL", "http://chromadb:8000")
    try:
        logger.info(f"chroma_url: {chroma_url}")
        response = requests.get(f"{chroma_url}/api/v2/heartbeat")
        return {"status": "success", "chromadb_response": response.json()}
    except Exception as e:
        return {"status": "error", "url": chroma_url, "error": str(e)}

@app.post("/api/kb/load")
@limiter.limit("5/minute")
async def upload_knowledge_base(request: Request, files: List[UploadFile] = File(...)):
    """
    Upload files to the knowledge base
    
    Args:
        files: List of files to upload
        
    Returns:
        Status for each file
    """
    logger.info("Uploading files to knowledge base", num_files=len(files))
    
    results = {}
    
    for file in files:
        if not file.filename.endswith(('.txt', '.md')):
            results[file.filename] = {"status": "error", "message": "Only .txt and .md files are supported"}
            continue
        
        try:
            # Save file
            file_path = os.path.join("kb_files", file.filename)
            content = await file.read()
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Index file
            success = index_file(file_path)
            
            if success:
                results[file.filename] = {"status": "success"}
            else:
                results[file.filename] = {"status": "error", "message": "Failed to index file"}
                
        except Exception as e:
            logger.error("Error processing file", file=file.filename, error=str(e))
            results[file.filename] = {"status": "error", "message": str(e)}
    
    return results


@app.delete("/api/kb/delete/{filename}")
async def delete_from_knowledge_base(filename: str):
    try:
        chroma_client = get_chroma_client()
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Delete all documents with this filename as source
        collection.delete(where={"source": filename})
        
        # Optionally delete the physical file
        file_path = os.path.join("kb_files", filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"status": "success", "message": f"Deleted {filename} from knowledge base"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(
    request: Request, 
    chat_request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat endpoint
    
    Args:
        request: FastAPI Request object
        chat_request: ChatRequest object with query and optional session_id
        db: Database session
        
    Returns:
        ChatResponse with answer, sources and session_id
    """
    query = chat_request.query
    session_id = chat_request.session_id or str(uuid.uuid4())
    
    logger.info("Chat request", session_id=session_id, query_length=len(query))
    
    try:
        # Get or create conversation in database
        conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
        if not conversation:
            conversation = Conversation(session_id=session_id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        
        # Get embedding for the query
        query_embedding = get_embeddings([query])[0]
        
        # Connect to Chroma and get collection
        chroma_client = get_chroma_client()
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Query Chroma for relevant chunks
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=TOP_K,
            include=["documents", "metadatas"]
        )
        
        # Extract documents and their sources
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        # Join chunks for context
        current_context = "\n\n".join(documents)
        
        # Get sources
        sources = [meta.get("source", "unknown") for meta in metadatas]
        unique_sources = list(set(sources))
        
        # Get conversation history from database, limited to last CONTEXT_MEMORY messages
        messages_history = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.timestamp.desc())
            .limit(CONTEXT_MEMORY * 2)  # Get pairs of messages
            .all()
        )
        messages_history.reverse()  # Reverse to get chronological order
        
        # Prepare messages for OpenAI
        openai_messages = [
            {"role": "system", "content": SYSTEM_PROMPT.replace("{context}", current_context)}
        ]
        
        # Add conversation history
        for msg in messages_history:
            openai_messages.append({"role": msg.role, "content": msg.content})
        
        # Add current query
        openai_messages.append({"role": "user", "content": query})
        
        # Call OpenAI chat completion
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=openai_messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
            frequency_penalty=FREQUENCY_PENALTY,
            presence_penalty=PRESENCE_PENALTY
        )
        
        # Extract response
        answer = response.choices[0].message.content

        if RESPONSE_PREFIX:
            answer = f"{answer}\n\n{RESPONSE_PREFIX}"
        
        # Save user message to database
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=query,
            sources=None
        )
        db.add(user_message)
        
        # Save assistant message to database
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            sources=json.dumps(unique_sources) if unique_sources else None
        )
        db.add(assistant_message)
        
        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()
        db.commit()
        
        # Return response
        return ChatResponse(
            answer=answer,
            sources=unique_sources,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error("Error in chat endpoint", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str, db: Session = Depends(get_db)):
    """
    Get conversation history by session ID
    
    Args:
        session_id: Session ID of the conversation
        db: Database session
        
    Returns:
        Conversation history
    """
    try:
        conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.timestamp).all()
        
        return {
            "session_id": conversation.session_id,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [msg.to_dict() for msg in messages]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving conversation", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))

# Add an endpoint to list all conversations
@app.get("/api/conversations")
async def list_conversations(db: Session = Depends(get_db)):
    """
    List all conversations
    
    Args:
        db: Database session
        
    Returns:
        List of conversations
    """
    try:
        conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
        return {
            "conversations": [
                {
                    "session_id": conv.session_id,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": len(conv.messages)
                }
                for conv in conversations
            ]
        }
    except Exception as e:
        logger.error("Error listing conversations", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/raw-http")
def debug_raw_http():
    import requests
    from urllib.parse import urlparse
    
    url = os.getenv("CHROMA_SERVER_URL", "http://chromadb:8000")
    try:
        # Try a basic health endpoint
        response = requests.get(f"{url}/api/v2/heartbeat", timeout=5)
        return {
            "status": "success",
            "url": url,
            "response_code": response.status_code,
            "response_text": response.text[:100]
        }
    except Exception as e:
        return {
            "status": "error",
            "url": url,
            "error": str(e)
        }

@app.get("/api/kb/list")
async def list_knowledge_base_files():
    """List all files in the knowledge base"""
    try:
        files = []
        kb_dir = "kb_files"
        
        if os.path.exists(kb_dir):
            for filename in os.listdir(kb_dir):
                if filename.endswith(('.txt', '.md')):
                    file_path = os.path.join(kb_dir, filename)
                    file_stat = os.stat(file_path)
                    files.append({
                        "filename": filename,
                        "size": file_stat.st_size,
                        "modified": file_stat.st_mtime
                    })
        
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.delete("/api/kb/delete-all")
async def delete_all_from_knowledge_base():
    """Delete all files from the knowledge base"""
    try:
        # Connect to ChromaDB and delete the entire collection
        chroma_client = get_chroma_client()
        try:
            chroma_client.delete_collection(name=COLLECTION_NAME)
            # Recreate empty collection
            chroma_client.create_collection(name=COLLECTION_NAME)
        except:
            pass  # Collection might not exist
        
        return {"status": "success", "message": "Knowledge base cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/kb/info/{filename}")
async def get_file_info(filename: str):
    """Get information about a specific file in the knowledge base"""
    try:
        file_path = os.path.join("kb_files", filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get file stats
        file_stat = os.stat(file_path)
        
        # Get chunk count from ChromaDB
        chroma_client = get_chroma_client()
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        results = collection.get(where={"source": filename})
        chunk_count = len(results['ids']) if results['ids'] else 0
        
        return {
            "filename": filename,
            "size": file_stat.st_size,
            "modified": file_stat.st_mtime,
            "chunk_count": chunk_count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.delete("/api/kb/delete/{filename}")
async def delete_from_knowledge_base(filename: str):
    try:
        chroma_client = get_chroma_client()
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Delete all documents with this filename as source
        collection.delete(where={"source": filename})
        
        # Optionally delete the physical file
        file_path = os.path.join("kb_files", filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return {"status": "success", "message": f"Deleted {filename} from knowledge base"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/kb/list-documents")
async def list_chromadb_documents():
    """List all unique source documents in ChromaDB"""
    try:
        chroma_client = get_chroma_client()
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Get all documents
        results = collection.get()
        
        # Extract unique sources
        sources = set()
        for metadata in results['metadatas']:
            if metadata and 'source' in metadata:
                sources.add(metadata['source'])
        
        return {"sources": list(sources)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/kb/status")
async def get_kb_status():
    """Get knowledge base status"""
    try:
        # Get ChromaDB stats
        chroma_client = get_chroma_client()
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Get all documents
        results = collection.get()
        
        # Count documents and unique sources
        total_documents = len(results['ids']) if 'ids' in results else 0
        sources = set()
        if 'metadatas' in results and results['metadatas']:
            for metadata in results['metadatas']:
                if metadata and 'source' in metadata:
                    sources.add(metadata['source'])
        
        return {
            "total_chunks": total_documents,
            "unique_files": len(sources),
            "files": list(sources)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api:app", host="0.0.0.0", port=port, reload=False)