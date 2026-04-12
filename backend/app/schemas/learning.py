from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    data_dir: str | None = None


class ChatRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)
    mode: Literal["socratic", "quiz"] = "socratic"
    attachments: list[dict] = Field(default_factory=list)


class ChatResponse(BaseModel):
    query: str
    mode: str
    result: dict
    retrieval: list[dict]


class QuizSubmitRequest(BaseModel):
    node_id: str
    question: str
    expected_answer: str
    user_answer: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class QuizSubmitResponse(BaseModel):
    is_correct: bool
    updated_mastery: dict
