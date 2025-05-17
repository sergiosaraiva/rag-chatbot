from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.database import Base
import json
import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base

class ChatRequest(BaseModel):
    """
    Model for chat request
    """
    session_id: Optional[str] = Field(None, description="Session ID for conversation history")
    query: str = Field(..., description="User query")

class ChatResponse(BaseModel):
    """
    Model for chat response
    """
    answer: str = Field(..., description="Answer to the user query")
    sources: List[str] = Field(default_factory=list, description="Source documents used for the answer")
    session_id: str = Field(..., description="Session ID for conversation tracking")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String, index=True)  # "user" or "assistant"
    content = Column(Text)
    sources = Column(Text, nullable=True)  # JSON string of sources
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")
    
    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "sources": json.loads(self.sources) if self.sources else None,
            "timestamp": self.timestamp.isoformat()
        }