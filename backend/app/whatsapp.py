# backend/app/whatsapp.py
import os
import json
import hmac
import hashlib
import requests
import logging
import fnmatch
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import get_db
from .models import ChatRequest, ChatResponse
from .rag import chat as rag_chat
from pydantic import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Load WhatsApp credentials from environment
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
WHATSAPP_VERSION = os.getenv("WHATSAPP_VERSION", "v17.0")
WHATSAPP_NUMBER_FILTER = os.getenv("WHATSAPP_NUMBER_FILTER", "")

# Models for WhatsApp API
class WhatsAppTextMessage(BaseModel):
   body: str

class WhatsAppMessage(BaseModel):
   messaging_product: str = "whatsapp"
   recipient_type: str = "individual"
   to: str
   type: str = "text"
   text: WhatsAppTextMessage

class TestWebhookPayload(BaseModel):
    entry: list = [{"changes": [{"value": {"messages": [{"from": "5551234567", "type": "text", "id": "test123", "text": {"body": "Test message"}}]}}]}]

def is_whatsapp_configured():
   """Check if WhatsApp integration is properly configured"""
   return all([WHATSAPP_TOKEN, WHATSAPP_APP_SECRET, WHATSAPP_PHONE_ID])

# Initialize router with prefix
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

# Dependency to verify WhatsApp configuration
async def verify_whatsapp_config():
   if not is_whatsapp_configured():
       raise HTTPException(
           status_code=503, 
           detail="WhatsApp integration not configured"
       )

async def verify_signature(request: Request, x_hub_signature_256: Optional[str] = Header(None)):
   """Verify that the request is from Meta with the correct signature"""
   if not WHATSAPP_APP_SECRET:
       return True  # Skip verification if app secret not configured
   
   if not x_hub_signature_256:
       raise HTTPException(status_code=401, detail="X-Hub-Signature-256 header missing")
   
   # Get request body as bytes
   request_body = await request.body()
   
   # Calculate the expected signature
   expected_signature = hmac.new(
       WHATSAPP_APP_SECRET.encode(),
       msg=request_body,
       digestmod=hashlib.sha256
   ).hexdigest()
   
   # Compare signatures
   actual_signature = x_hub_signature_256.replace("sha256=", "")
   if not hmac.compare_digest(expected_signature, actual_signature):
       raise HTTPException(status_code=401, detail="Invalid signature")
   
   return True

def is_number_allowed(phone_number):
    """Check if a phone number is allowed based on filter patterns"""
    if not WHATSAPP_NUMBER_FILTER:
        return True  # Allow all numbers if no filter is set
    
    # Clean the input phone number
    phone_number = phone_number.strip().replace(" ", "")
    
    # Clean and split filter patterns
    filter_patterns = [pattern.strip().replace(" ", "") for pattern in WHATSAPP_NUMBER_FILTER.split(',')]
    
    for pattern in filter_patterns:
        if fnmatch.fnmatch(phone_number, pattern):
            return True
    
    return False

@router.get("/webhook")
async def verify_webhook(
   request: Request,
   _: bool = Depends(verify_whatsapp_config)
):
   """Verify webhook endpoint for WhatsApp webhook setup"""
   # Get query parameters
   query_params = request.query_params
   verify_token = query_params.get("hub.verify_token")
   challenge = query_params.get("hub.challenge")
   
   # Check verify token
   if verify_token != WHATSAPP_TOKEN:
       logger.warning(f"Invalid verify token: {verify_token}")
       raise HTTPException(status_code=401, detail="Invalid verify token")
   
   # Return challenge
   logger.info(f"WhatsApp webhook verified successfully")
   return Response(content=challenge, media_type="text/plain")

@router.post("/webhook")
async def receive_message(
   request: Request, 
   db: Session = Depends(get_db),
   _: bool = Depends(verify_whatsapp_config)
):
    # Verify signature and parse request body (keep existing code)
    await verify_signature(request)
    body = await request.json()
    logger.debug(f"Received webhook: {json.dumps(body, indent=2)}")
    
    try:
        # Extract message data from the webhook
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        messages = value.get("messages", [])
        if not messages:
            logger.debug("Webhook received but no messages found")
            return {"status": "no messages"}
        
        # Process each message
        for message in messages:
            # Only process text messages
            if message.get("type") != "text":
                logger.debug(f"Skipping non-text message of type: {message.get('type')}")
                continue
            
            # Extract message data
            from_number = message.get("from")
            message_id = message.get("id")
            text = message.get("text", {}).get("body", "")
            
            # Check if this number is allowed
            if not is_number_allowed(from_number):
                logger.info(f"Ignoring message from filtered number: {from_number}")
                continue
            
            logger.info(f"Processing WhatsApp message from {from_number}: {text[:50]}...")
            
            # Rest of your existing code...
            session_id = f"whatsapp_{from_number}"
            
            # Process the message through RAG system
            chat_request = ChatRequest(
                query=text,
                session_id=session_id
            )
            
            # Get response from RAG system
            chat_response = await rag_chat(request, chat_request, db)
            
            # Send response back to WhatsApp
            await send_whatsapp_message(from_number, chat_response.answer)
            logger.info(f"Response sent to {from_number}")
        
        return {"status": "success"}
    
    except Exception as e:
        logger.error(f"Error processing WhatsApp message: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def send_whatsapp_message(to: str, text: str):
   """Send a message to a WhatsApp user"""
   if not is_whatsapp_configured():
       logger.warning("WhatsApp integration not configured, skipping message send")
       return {"status": "skipped", "reason": "not_configured"}
   
   url = f"https://graph.facebook.com/{WHATSAPP_VERSION}/{WHATSAPP_PHONE_ID}/messages"
   
   headers = {
       "Content-Type": "application/json",
       "Authorization": f"Bearer {WHATSAPP_TOKEN}"
   }
   
   # WhatsApp has a limit on message length, so we might need to split long messages
   # Maximum message length is around 4096 characters, but let's be conservative
   MAX_MESSAGE_LENGTH = 3000
   
   if len(text) <= MAX_MESSAGE_LENGTH:
       messages = [text]
   else:
       # Split the message at appropriate points
       messages = []
       remaining_text = text
       
       while len(remaining_text) > MAX_MESSAGE_LENGTH:
           # Find a good breaking point
           split_point = remaining_text.rfind('\n', 0, MAX_MESSAGE_LENGTH)
           if split_point == -1:
               split_point = remaining_text.rfind('. ', 0, MAX_MESSAGE_LENGTH)
           if split_point == -1:
               split_point = remaining_text.rfind(' ', 0, MAX_MESSAGE_LENGTH)
           if split_point == -1:
               split_point = MAX_MESSAGE_LENGTH
           
           messages.append(remaining_text[:split_point])
           remaining_text = remaining_text[split_point:].lstrip()
       
       if remaining_text:
           messages.append(remaining_text)
   
   # Send each part of the message
   responses = []
   for msg_part in messages:
       message = WhatsAppMessage(
           to=to,
           text=WhatsAppTextMessage(body=msg_part)
       )
       
       try:
           response = requests.post(url, headers=headers, data=message.json())
           response.raise_for_status()
           responses.append(response.json())
           
           # Slight delay to prevent rate limiting
           import asyncio
           await asyncio.sleep(0.5)
           
       except Exception as e:
           logger.error(f"Error sending WhatsApp message: {str(e)}")
           if hasattr(e, 'response') and e.response:
               logger.error(f"Response: {e.response.text}")
           responses.append({"error": str(e)})
   
   return responses

@router.get("/status")
async def whatsapp_status():
   """Check WhatsApp integration status"""
   return {
       "configured": is_whatsapp_configured(),
       "token_configured": bool(WHATSAPP_TOKEN),
       "app_secret_configured": bool(WHATSAPP_APP_SECRET),
       "phone_id_configured": bool(WHATSAPP_PHONE_ID),
       "version": WHATSAPP_VERSION
   }

@router.post("/test-webhook")
async def test_webhook(
    payload: TestWebhookPayload,
    db: Session = Depends(get_db)
):
    """Test endpoint with explicit schema for webhook testing"""
    # Skip signature verification for testing
    try:
        # Process the message directly
        from_number = payload.entry[0]["changes"][0]["value"]["messages"][0]["from"]
        message_text = payload.entry[0]["changes"][0]["value"]["messages"][0]["text"]["body"]
        message_id = payload.entry[0]["changes"][0]["value"]["messages"][0]["id"]
        
        # Check if number is allowed
        if not is_number_allowed(from_number):
            return {"status": "filtered", "reason": f"Number {from_number} not in allowed list"}
            
        # Create session ID and process through RAG
        session_id = f"whatsapp_{from_number}"
        chat_request = ChatRequest(query=message_text, session_id=session_id)
        
        # Get response
        chat_response = await rag_chat(None, chat_request, db)
        
        # Return the response that would be sent
        return {
            "status": "success",
            "would_send_to": from_number,
            "message": chat_response.answer
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}