from __future__ import annotations

from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    id: str
    name: str
    content_type: str
    size: int


class FileAttachment(BaseModel):
    id: str
    name: str
    content_type: str
    size: int = Field(default=0, ge=0)
