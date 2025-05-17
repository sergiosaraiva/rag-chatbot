# backend/app/rag.py
import os
import uuid
import structlog
from typing import List, Dict, Optional, Any
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from openai import OpenAI
from .database import get_db

from .models import ChatRequest, ChatResponse
from .chunk_and_index import get_chroma_client, get_embeddings
import datetime
import json

# Configure logging
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

# Context memory
CONTEXT_MEMORY = int(os.getenv("CONTEXT_MEMORY", "20"))

# Configure OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Import database models directly
from app.api import Conversation, Message

async def chat(
    request: Request, 
    chat_request: ChatRequest,
    db: Session = Depends(get_db)
) -> ChatResponse:
    """
    Chat endpoint logic
    
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
        conversation.updated_at = datetime.datetime.utcnow()
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