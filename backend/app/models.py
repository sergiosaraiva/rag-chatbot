from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


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
