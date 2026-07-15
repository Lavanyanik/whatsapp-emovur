"""Pydantic schemas for generic WhatsApp messaging requests and responses."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
import re


class MessageRequest(BaseModel):
    type: str = Field(..., description="Message type: template, text, image, document, video, audio, or interactive")
    to: str = Field(..., description="Recipient phone number in E.164 or local format")
    template_name: Optional[str] = Field(None, description="Approved template name for template messages")
    language: Optional[str] = Field(None, description="Language code for template messages, e.g. en_US")
    components: Optional[List[Dict[str, Any]]] = Field(None, description="Optional template components")
    text: Optional[str] = Field(None, description="Text message body")
    media_id: Optional[str] = Field(None, description="Media object ID for image, document, video, or audio messages")
    caption: Optional[str] = Field(None, description="Optional caption for media messages")
    interactive: Optional[Dict[str, Any]] = Field(None, description="Interactive payload for buttons or list messages")

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("to")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        pattern = re.compile(r"^\+?[0-9]{6,15}$")
        if not pattern.match(value):
            raise ValueError("to must be digits, optionally prefixed with +, length 6-15")
        return value

    @model_validator(mode="after")
    def validate_message_payload(self):
        msg_type = self.type
        if msg_type == "template":
            if not self.template_name or not self.language:
                raise ValueError("template_name and language are required for template messages")
        elif msg_type == "text":
            if not self.text:
                raise ValueError("text is required for text messages")
        elif msg_type in {"image", "document", "video", "audio"}:
            if not self.media_id:
                raise ValueError(f"media_id is required for {msg_type} messages")
        elif msg_type == "interactive":
            if not self.interactive:
                raise ValueError("interactive payload is required for interactive messages")
        else:
            raise ValueError(f"unsupported message type: {msg_type}")
        return self


class MessageResponse(BaseModel):
    status: str = Field(..., description="Result status")
    upstream_status_code: int = Field(..., description="Emovur response status code")
    data: Any = Field(..., description="Emovur response payload")


__all__ = ["MessageRequest", "MessageResponse"]
