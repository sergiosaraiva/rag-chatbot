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

from app.models import ChatRequest, ChatResponse
from app.chunk_and_index import index_file, get_chroma_client, get_embeddings

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
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
TOP_P = float(os.getenv("TOP_P", "0.9"))
FREQUENCY_PENALTY = float(os.getenv("FREQUENCY_PENALTY", "0.0"))
PRESENCE_PENALTY = float(os.getenv("PRESENCE_PENALTY", "0.0"))
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "text-embedding-ada-002")

# Chroma configuration
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "kb_default")
TOP_K = int(os.getenv("TOP_K", "5"))

# System prompt template
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", 
                         "You are an expert assistant. Use the following context to answer:\n\n{context}\n\nAnswer conversationally.")

# Configure OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# In-memory session history
session_history: Dict[str, List[Dict[str, str]]] = {}

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


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat(request: Request, chat_request: ChatRequest):
    """
    Chat endpoint
    
    Args:
        request: FastAPI Request object
        chat_request: ChatRequest object with query and optional session_id
        
    Returns:
        ChatResponse with answer, sources and session_id
    """
    query = chat_request.query
    session_id = chat_request.session_id or str(uuid.uuid4())
    
    logger.info("Chat request", session_id=session_id, query_length=len(query))
    
    try:
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
        context = "\n\n".join(documents)
        
        # Get sources
        sources = [meta.get("source", "unknown") for meta in metadatas]
        unique_sources = list(set(sources))
        
        # Initialize session history if needed
        if session_id not in session_history:
            session_history[session_id] = []
        
        # Prepare messages for OpenAI
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.replace("{context}", context)}
        ]
        
        # Add conversation history
        for msg in session_history[session_id]:
            messages.append(msg)
        
        # Add current query
        messages.append({"role": "user", "content": query})
        
        # Call OpenAI chat completion
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
            frequency_penalty=FREQUENCY_PENALTY,
            presence_penalty=PRESENCE_PENALTY
        )
        
        # Extract response
        answer = response.choices[0].message.content
        
        # Update session history
        session_history[session_id].append({"role": "user", "content": query})
        session_history[session_id].append({"role": "assistant", "content": answer})
        
        # Limit history length
        if len(session_history[session_id]) > 10:
            session_history[session_id] = session_history[session_id][-10:]
        
        # Return response
        return ChatResponse(
            answer=answer,
            sources=unique_sources,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error("Error in chat endpoint", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
