# backend/app/rag.py
import os
import uuid
import structlog
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from openai import OpenAI
from .database import get_db

from app.models import Conversation, Message
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

CONTEXT_MEMORY = int(os.getenv("CONTEXT_MEMORY", "20"))

# System prompt template
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", 
                         "You are an expert assistant. Use the following context to answer:\n\n{context}\n\nAnswer conversationally. If you don't know the answer based on the provided context, say so.")

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "70.0"))  # Default 70%
CONFIDENCE_PROMPT = os.getenv("CONFIDENCE_PROMPT", """
Evaluate your confidence in the answer you just provided on a scale of 0-100%.
Consider these factors:
1. How directly the retrieved documents address the query
2. Whether the information is complete or partial
3. If there are contradictions in the sources
4. How specific vs. general your answer is

First explain your reasoning, then output only a number between 0-100 on the final line.
""")
INCLUDE_CONFIDENCE_REASON = os.getenv("INCLUDE_CONFIDENCE_REASON", "false").lower() == "true"
EXPOSE_CONFIDENCE_SCORE = os.getenv("EXPOSE_CONFIDENCE_SCORE", "false").lower() == "true"

ENABLE_DATABASE_STORAGE = os.getenv("ENABLE_DATABASE_STORAGE", "true").lower() == "true"

# Configure OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

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
       # Get or create conversation in database only if database storage is enabled
       conversation = None
       if ENABLE_DATABASE_STORAGE:
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
       
       # Initialize messages_history as empty
       messages_history = []
       
       # Get conversation history from database only if database storage is enabled
       if ENABLE_DATABASE_STORAGE and conversation:
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
           
       # Evaluate confidence in the answer
       confidence_score, confidence_reason = await evaluate_confidence(
           query=query,
           context=current_context,
           answer=answer,
           client=client
       )
       
       # Only save to database if database storage is enabled
       if ENABLE_DATABASE_STORAGE and conversation:
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
               sources=json.dumps(unique_sources) if unique_sources else None,
               confidence_score=confidence_score,
               confidence_reason=confidence_reason if INCLUDE_CONFIDENCE_REASON else None
           )
           db.add(assistant_message)
           
           logger.info(f"Confidence score: {confidence_score}")
           # Update conversation status based on confidence threshold
           if confidence_score < CONFIDENCE_THRESHOLD:
               conversation.status = "waiting_for_manual"
           else:
               conversation.status = "waiting_for_user"
               
           # Update conversation timestamp
           conversation.updated_at = datetime.datetime.utcnow()
           db.commit()
       
       # Return response with optional confidence score
       response_data = {
           "answer": answer,
           "sources": unique_sources,
           "session_id": session_id
       }
       
       if EXPOSE_CONFIDENCE_SCORE:
           response_data["confidence_score"] = confidence_score
           
       return ChatResponse(**response_data)
       
   except Exception as e:
       logger.error("Error in chat endpoint", error=str(e), session_id=session_id)
       raise HTTPException(status_code=500, detail=str(e))

    
async def evaluate_confidence(query: str, context: str, answer: str, client: OpenAI) -> tuple[float, str]:
    """
    Evaluate confidence in RAG answer using LLM self-assessment
    
    Returns:
        Tuple of (confidence_score, confidence_reasoning)
    """
    try:
        eval_messages = [
            {"role": "system", "content": "You are an expert evaluator assessing answer quality and confidence."},
            {"role": "user", "content": f"QUERY: {query}\n\nCONTEXT USED: {context}\n\nGENERATED ANSWER: {answer}\n\n{CONFIDENCE_PROMPT}"}
        ]
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=eval_messages,
            temperature=0.1  # Lower temperature for consistent evaluation
        )
        
        reasoning = response.choices[0].message.content
        
        # Extract confidence score from last line
        score_text = reasoning.strip().split('\n')[-1].strip('%')
        try:
            confidence_score = float(score_text)
            # Ensure score is within valid range
            confidence_score = max(0, min(100, confidence_score))
        except ValueError:
            # Fallback if unable to extract score
            confidence_score = 50.0

        logger.info(f"Confidence evaluation: {confidence_score}% - {reasoning[:100]}...")
        return confidence_score, reasoning
    except Exception as e:
        logger.error(f"Error evaluating confidence: {str(e)}")
        return 50.0, f"Error evaluating confidence: {str(e)}"