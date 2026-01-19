#!/usr/bin/env python
# coding: utf-8

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]

# --------- Multimodal message parts ---------

class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ImagePart(BaseModel):
    """
    image can be:
      - data URL: "data:image/png;base64,...."
      - raw base64: "iVBORw0K..."
      - http(s) URL: "https://..."
    """
    type: Literal["image"] = "image"
    data: str = Field(..., description="dataURL/base64/http(s) url")
    mime_type: Optional[str] = Field(default=None, description="e.g. image/png")

ContentPart = Union[TextPart, ImagePart]

class ChatMessage(BaseModel):
    role: Role
    # For user/system/assistant/tool: you can use plain string or parts list
    content: Union[str, List[ContentPart]]


# --------- Requests / Responses ---------

class ChatRequest(BaseModel):
    """
    One turn request:
      - session_id: identify a conversation
      - language: response language ("en" or "zh")
      - system_prompt: optional; if provided, server will upsert it into the session context
      - message: the current user message (text+images supported)
      - meta: arbitrary
      - history: optional; if provided, use frontend-managed history (stateless mode)
                 if not provided or empty, use backend session management (original mode)
    """
    session_id: str = Field(default="default")
    language: Optional[str] = Field(default=None, description="Response language: 'en' or 'zh'")
    system_prompt: Optional[str] = None
    message: ChatMessage
    meta: Dict[str, Any] = Field(default_factory=dict)
    # Frontend-managed history mode: if provided, backend becomes stateless
    history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Optional conversation history from frontend. If provided, backend uses this instead of session storage."
    )

class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    history: List[Dict[str, Any]]
    usage: Usage = Field(default_factory=Usage)
    result_type: str = "answer"   # "answer" / "error"

class ResetRequest(BaseModel):
    session_id: str


class CancelRequest(BaseModel):
    """Cancel an ongoing request for a session."""
    session_id: str


class CancelResponse(BaseModel):
    """Response for cancel request."""
    session_id: str
    cancelled: bool
    reason: str
    timestamp: int
