import os
import datetime
import structlog
from typing import List
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from openai import OpenAI
from dotenv import load_dotenv
from app.database import get_db
from app.whatsapp import router as whatsapp_router
from app.models import Conversation, Message
from app.database import ENABLE_DATABASE_STORAGE

from sqlalchemy.orm import Session
from fastapi import Depends
from app.rag import chat

from app.models import ChatRequest, ChatResponse
from app.chunk_and_index import index_file, get_chroma_client, get_embeddings

import logging
logging.basicConfig(level=logging.INFO)
from app.whatsapp import router as whatsapp_router, is_whatsapp_configured

from app.database import init_db
init_db()

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

app.include_router(whatsapp_router)

# Ensure kb_files directory exists
os.makedirs("kb_files", exist_ok=True)

# Add this endpoint to debug environment variables
@app.get("/api/debug/env")
def debug_env():
    """Debug environment variables"""
    return {
        "OPENAI_API_KEY": OPENAI_API_KEY[:3] + "..." if OPENAI_API_KEY else None,
        "MODEL_NAME": MODEL_NAME,
        "TEMPERATURE": TEMPERATURE,
        "MAX_TOKENS": MAX_TOKENS,
        "EMBED_MODEL_NAME": EMBED_MODEL_NAME,
        "CHROMA_SERVER_URL": os.getenv("CHROMA_SERVER_URL"),
        "COLLECTION_NAME": COLLECTION_NAME,
        "DATABASE_URL": os.getenv("DATABASE_URL")
    }

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


from app.rag import chat as rag_chat

@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat_endpoint(  # Rename the function
    request: Request, 
    chat_request: ChatRequest,
    db: Session = Depends(get_db)
):
    return await rag_chat(request, chat_request, db)

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
    # Check if database storage is enabled
    if not ENABLE_DATABASE_STORAGE:
        return {
            "session_id": session_id,
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "messages": []
        }
        
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

# Modify the list_conversations function in api.py
@app.get("/api/conversations")
async def list_conversations(db: Session = Depends(get_db)):
    """
    List all conversations
    
    Args:
        db: Database session
        
    Returns:
        List of conversations
    """
    # Check if database storage is enabled
    if not ENABLE_DATABASE_STORAGE:
        return {"conversations": []}
        
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