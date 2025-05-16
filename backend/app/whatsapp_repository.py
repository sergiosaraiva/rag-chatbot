# backend/app/whatsapp_repository.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from app.whatsapp_db import Contact, Conversation, Message, Response, ResponseTemplate

class WhatsAppRepository:
    def __init__(self, db: Session):
        self.db = db
    
    # Contact methods
    def get_contact_by_phone(self, phone: str) -> Optional[Contact]:
        return self.db.query(Contact).filter(Contact.phone == phone).first()
    
    def create_contact(self, contact_data: Dict[str, Any]) -> Contact:
        contact = Contact(**contact_data)
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact
    
    def update_contact(self, contact_id: int, contact_data: Dict[str, Any]) -> Optional[Contact]:
        contact = self.db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            return None
        
        for key, value in contact_data.items():
            setattr(contact, key, value)
        
        self.db.commit()
        self.db.refresh(contact)
        return contact
    
    def get_or_create_contact(self, phone: str, name: Optional[str] = None) -> Contact:
        contact = self.get_contact_by_phone(phone)
        if not contact:
            contact_data = {
                "phone": phone,
                "name": name or phone
            }
            contact = self.create_contact(contact_data)
        return contact
    
    # Conversation methods
    def get_conversation_by_whatsapp_id(self, whatsapp_chat_id: str) -> Optional[Conversation]:
        return self.db.query(Conversation).filter(
            Conversation.whatsapp_chat_id == whatsapp_chat_id
        ).first()
    
    def create_conversation(self, conversation_data: Dict[str, Any]) -> Conversation:
        conversation = Conversation(**conversation_data)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def get_or_create_conversation(self, contact_id: int, whatsapp_chat_id: str) -> Conversation:
        conversation = self.get_conversation_by_whatsapp_id(whatsapp_chat_id)
        if not conversation:
            conversation_data = {
                "contact_id": contact_id,
                "whatsapp_chat_id": whatsapp_chat_id,
                "status": "unread"
            }
            conversation = self.create_conversation(conversation_data)
        return conversation
    
    def update_conversation_status(self, conversation_id: int, status: str) -> Optional[Conversation]:
        conversation = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return None
        
        conversation.status = status
        conversation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def set_followup_time(self, conversation_id: int, followup_time: datetime) -> Optional[Conversation]:
        conversation = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return None
            
        conversation.scheduled_followup = followup_time
        conversation.status = "skipped"  # Mark as skipped until followup time
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
    
    def get_unprocessed_conversations(self, limit: int = 10) -> List[Conversation]:
        """Get conversations that need to be processed, prioritized by contact priority and time"""
        return self.db.query(Conversation).join(Contact).filter(
            Conversation.status.in_(["unread", "skipped"])
        ).order_by(
            # Order by priority (high first), then scheduled followups, then updated time
            desc(Contact.priority == "high"),
            Conversation.scheduled_followup.asc().nullslast(),
            Conversation.updated_at.asc()
        ).limit(limit).all()
    
    def get_conversations_due_for_followup(self) -> List[Conversation]:
        """Get conversations that are scheduled for followup and the time has come"""
        now = datetime.utcnow()
        return self.db.query(Conversation).filter(
            Conversation.status == "skipped",
            Conversation.scheduled_followup <= now
        ).all()
    
    # Message methods
    def create_message(self, message_data: Dict[str, Any]) -> Message:
        message = Message(**message_data)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
    
    def get_message_by_whatsapp_id(self, whatsapp_message_id: str) -> Optional[Message]:
        return self.db.query(Message).filter(
            Message.whatsapp_message_id == whatsapp_message_id
        ).first()
    
    def get_conversation_messages(self, conversation_id: int, limit: int = 20) -> List[Message]:
        """Get the most recent messages for a conversation"""
        return self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.desc()).limit(limit).all()
    
    def mark_message_as_processed(self, message_id: int) -> Optional[Message]:
        message = self.db.query(Message).filter(Message.id == message_id).first()
        if not message:
            return None
            
        message.processed = True
        self.db.commit()
        self.db.refresh(message)
        return message
    
    # Response methods
    def create_response(self, response_data: Dict[str, Any]) -> Response:
        response = Response(**response_data)
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)
        return response
    
    def update_response(self, response_id: int, response_data: Dict[str, Any]) -> Optional[Response]:
        response = self.db.query(Response).filter(Response.id == response_id).first()
        if not response:
            return None
            
        for key, value in response_data.items():
            setattr(response, key, value)
            
        self.db.commit()
        self.db.refresh(response)
        return response
    
    def mark_response_as_sent(self, response_id: int) -> Optional[Response]:
        response = self.db.query(Response).filter(Response.id == response_id).first()
        if not response:
            return None
            
        response.status = "sent"
        response.sent_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(response)
        return response
    
    # Template methods
    def get_templates(self, category: Optional[str] = None, tags: Optional[List[str]] = None) -> List[ResponseTemplate]:
        query = self.db.query(ResponseTemplate).filter(ResponseTemplate.is_active == True)
        
        if category:
            query = query.filter(ResponseTemplate.category == category)
            
        if tags:
            # Filter templates that have at least one of the requested tags
            # This requires database-specific JSON handling, here's a generic approach
            for tag in tags:
                query = query.filter(ResponseTemplate.tags.contains(tag))
                
        return query.order_by(ResponseTemplate.name).all()
    
    def create_template(self, template_data: Dict[str, Any]) -> ResponseTemplate:
        template = ResponseTemplate(**template_data)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template
    
    def update_template(self, template_id: int, template_data: Dict[str, Any]) -> Optional[ResponseTemplate]:
        template = self.db.query(ResponseTemplate).filter(ResponseTemplate.id == template_id).first()
        if not template:
            return None
            
        for key, value in template_data.items():
            setattr(template, key, value)
            
        self.db.commit()
        self.db.refresh(template)
        return template
    
    # Stats and analytics methods
    def get_conversation_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get statistics about conversations in the past X days"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        total_conversations = self.db.query(func.count(Conversation.id)).filter(
            Conversation.created_at >= start_date
        ).scalar()
        
        status_counts = {}
        for status in ["unread", "read", "answered", "skipped", "dont_answer"]:
            count = self.db.query(func.count(Conversation.id)).filter(
                Conversation.created_at >= start_date,
                Conversation.status == status
            ).scalar()
            status_counts[status] = count
        
        # Messages per conversation (average)
        avg_messages = self.db.query(
            func.avg(
                self.db.query(func.count(Message.id))
                .filter(Message.conversation_id == Conversation.id)
                .correlate(Conversation)
                .scalar_subquery()
            )
        ).filter(
            Conversation.created_at >= start_date
        ).scalar() or 0
        
        return {
            "total_conversations": total_conversations,
            "status_counts": status_counts,
            "avg_messages_per_conversation": float(avg_messages)
        }
