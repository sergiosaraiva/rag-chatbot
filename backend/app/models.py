from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.database import Base
import json
import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum as SQLEnum
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


class ConversationStatus(str, Enum):
    WAITING_FOR_MANUAL = "waiting_for_manual"
    WAITING_FOR_USER = "waiting_for_user"
    CLOSED = "closed"
    
class MessageType(str, Enum):
    USER = "user"
    AUTO = "auto"
    MANUAL = "manual"

# Use them in your models like this:
class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    # Change this line
    status = Column(String, default=ConversationStatus.WAITING_FOR_USER.value)
    user_phone = Column(String, nullable=True)
    user_name = Column(String, nullable=True)
    
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    role = Column(String, index=True)
    content = Column(Text)
    sources = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    message_type = Column(String, default=MessageType.AUTO.value)
    
    conversation = relationship("Conversation", back_populates="messages")
    
    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "sources": json.loads(self.sources) if self.sources else None,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type
        }