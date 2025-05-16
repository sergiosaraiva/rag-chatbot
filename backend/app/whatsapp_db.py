# backend/app/whatsapp_db.py

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON, Boolean, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from app.database import Base

class Contact(Base):
    __tablename__ = "whatsapp_contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True)
    name = Column(String(255), nullable=True)
    profile_photo_url = Column(String(512), nullable=True)
    priority = Column(Enum("normal", "high", name="contact_priority"), default="normal")
    tags = Column(JSON, default=list)  # Store tags as JSON array
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_interaction = Column(DateTime, nullable=True)
    
    conversations = relationship("Conversation", back_populates="contact", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "profile_photo_url": self.profile_photo_url,
            "priority": self.priority,
            "tags": self.tags,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_interaction": self.last_interaction.isoformat() if self.last_interaction else None
        }


class Conversation(Base):
    __tablename__ = "whatsapp_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("whatsapp_contacts.id"), index=True)
    whatsapp_chat_id = Column(String(255), index=True, nullable=False)  # WhatsApp's chat identifier
    status = Column(
        Enum("unread", "read", "answered", "skipped", "dont_answer", name="conversation_status"),
        default="unread"
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scheduled_followup = Column(DateTime, nullable=True)
    
    contact = relationship("Contact", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    # Create an index on status and updated_at for efficient querying
    __table_args__ = (
        Index("idx_conversation_status_updated", status, updated_at),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "contact_id": self.contact_id,
            "whatsapp_chat_id": self.whatsapp_chat_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "scheduled_followup": self.scheduled_followup.isoformat() if self.scheduled_followup else None,
            "contact": self.contact.to_dict() if self.contact else None
        }


class Message(Base):
    __tablename__ = "whatsapp_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("whatsapp_conversations.id"), index=True)
    whatsapp_message_id = Column(String(255), index=True, nullable=False)  # WhatsApp's message identifier
    direction = Column(Enum("incoming", "outgoing", name="message_direction"))
    content_type = Column(Enum("text", "image", "video", "audio", "document", "location", "contact", "other", name="content_type"), default="text")
    content = Column(Text)
    media_url = Column(String(512), nullable=True)  # For media messages
    metadata = Column(JSON, nullable=True)  # Additional metadata about the message
    timestamp = Column(DateTime, index=True)
    processed = Column(Boolean, default=False)
    
    conversation = relationship("Conversation", back_populates="messages")
    responses = relationship("Response", back_populates="message", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "whatsapp_message_id": self.whatsapp_message_id,
            "direction": self.direction,
            "content_type": self.content_type,
            "content": self.content,
            "media_url": self.media_url,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "processed": self.processed
        }


class Response(Base):
    __tablename__ = "whatsapp_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("whatsapp_messages.id"), index=True)
    original_response = Column(Text)
    edited_response = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    sources = Column(JSON, nullable=True)  # Store sources from RAG as JSON
    template_id = Column(Integer, nullable=True)  # If response used a template
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    status = Column(
        Enum("draft", "edited", "sent", "failed", name="response_status"),
        default="draft"
    )
    
    message = relationship("Message", back_populates="responses")
    
    def to_dict(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "original_response": self.original_response,
            "edited_response": self.edited_response,
            "confidence_score": self.confidence_score,
            "sources": self.sources,
            "template_id": self.template_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status
        }


class ResponseTemplate(Base):
    __tablename__ = "whatsapp_response_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=list)  # Store tags as JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active
        }
