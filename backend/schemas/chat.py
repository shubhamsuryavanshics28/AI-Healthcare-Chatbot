"""
Pydantic Schemas for AI Chatbot and Conversation Management
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict


class MessageSendRequest(BaseModel):
    conversation_id: Optional[str] = None
    content: str = Field(..., min_length=1, max_length=3000, description="Patient message text")


class ChatCitation(BaseModel):
    title: str
    source: str
    section: Optional[str] = None
    url: Optional[str] = None
    relevance_score: Optional[float] = None


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    role: str
    content: str
    citations: Optional[List[ChatCitation]] = None
    safety_flags: Optional[dict] = None
    created_at: datetime


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []
