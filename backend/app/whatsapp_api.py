# backend/app/whatsapp_api.py

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.database import get_db
from app.whatsapp_service import WhatsAppService
from pydantic import BaseModel, Field
from datetime import datetime

# Define Pydantic models for request/response validation
class IncomingMessageRequest(BaseModel):
    phone: str
    name: Optional[str] = None
    chat_id: str
    message_id: str
    content: str
    content_type: str = "text"
    media_url: Optional[str] = None
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class EditResponseRequest(BaseModel):
    edited_text: str

class StatusUpdateRequest(BaseModel):
    status: str
    
class FollowupRequest(BaseModel):
    followup_time: datetime

# Create router
router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])

# Create endpoints
@router.post("/incoming-message")
async def process_incoming_message(
    message: IncomingMessageRequest,
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    result = service.process_incoming_message(message.dict())
    return result

@router.get("/conversations")
async def get_conversations(
    status: Optional[str] = Query(None, description="Filter by conversation status"),
    limit: int = Query(10, description="Maximum number of conversations to return"),
    skip: int = Query(0, description="Number of conversations to skip"),
    db: Session = Depends(get_db)
):
    # Implementation depends on additional filtering needed
    service = WhatsAppService(db)
    conversations = service.get_next_conversations(limit=limit)
    return {"conversations": conversations}

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int = Path(..., description="ID of the conversation"),
    message_limit: int = Query(10, description="Maximum number of messages to retrieve"),
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    context = service.get_conversation_context(conversation_id, message_limit=message_limit)
    if "error" in context:
        raise HTTPException(status_code=404, detail=context["error"])
    return context

@router.post("/responses/create")
async def create_response(
    message_id: int = Body(..., embed=True),
    rag_response: Dict[str, Any] = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    result = service.create_response_draft(message_id, rag_response)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.put("/responses/{response_id}/edit")
async def edit_response(
    response_id: int,
    request: EditResponseRequest,
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    result = service.edit_response(response_id, request.edited_text)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.post("/responses/{response_id}/send")
async def send_response(
    response_id: int,
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    result = service.send_response(response_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.put("/conversations/{conversation_id}/status")
async def update_conversation_status(
    conversation_id: int,
    request: StatusUpdateRequest,
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    result = service.update_conversation_status(conversation_id, request.status)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.post("/conversations/{conversation_id}/followup")
async def schedule_followup(
    conversation_id: int,
    request: FollowupRequest,
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    result = service.schedule_followup(conversation_id, request.followup_time)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/templates")
async def get_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    db: Session = Depends(get_db)
):
    tag_list = tags.split(",") if tags else None
    service = WhatsAppService(db)
    templates = service.get_response_templates(category, tag_list)
    return {"templates": templates}

@router.get("/stats")
async def get_stats(
    days: int = Query(30, description="Number of days to include in statistics"),
    db: Session = Depends(get_db)
):
    service = WhatsAppService(db)
    repo = service.repo
    stats = repo.get_conversation_stats(days=days)
    return stats

from fastapi import HTTPException, Response
from app.whatsapp_client import WhatsAppClient
import qrcode
import io

@router.get("/session/status")
async def get_session_status():
    """Get the current WhatsApp session status"""
    client = WhatsAppClient()
    return client.get_session_status()

@router.post("/session/logout")
async def logout():
    """Logout from WhatsApp"""
    client = WhatsAppClient()
    await client.logout()
    return {"status": "logged_out"}

@router.post("/session/initialize")
async def initialize():
    """Initialize the WhatsApp client"""
    client = WhatsAppClient()
    await client.initialize()
    return {"status": "initialization_started"}

@router.get("/session/qrcode")
async def get_qrcode():
    """Get the QR code as an image"""
    client = WhatsAppClient()
    status = client.get_session_status()
    
    if status["status"] != "qr_received" or not status["qr_code"]:
        raise HTTPException(status_code=404, detail="QR code not available")
    
    # Generate QR code image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(status["qr_code"])
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save image to bytes buffer
    buffer = io.BytesIO()
    img.save(buffer)
    buffer.seek(0)
    
    # Return the image
    return Response(content=buffer.getvalue(), media_type="image/png")
