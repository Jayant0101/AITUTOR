from __future__ import annotations

from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field


# ── MCQ Quiz Generation ────────────────────────────────────────────────────


class MCQGenerateRequest(BaseModel):
    topic: str = Field(..., description="Topic to quiz on (e.g. 'AI Basics')")
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    num_questions: int = Field(default=10, ge=1, le=20)


class MCQOption(BaseModel):
    index: int       # 0-3
    text: str


class MCQQuestion(BaseModel):
    id: int
    question: str
    options: List[str]          # ["A: ...", "B: ...", "C: ...", "D: ..."]
    correct_index: int          # 0-based index into options
    explanation: str


class MCQBatch(BaseModel):
    quiz_id: str
    topic: str
    difficulty: str
    questions: List[MCQQuestion]


# ── Quiz Session Submit ────────────────────────────────────────────────────


class QuizSessionSubmit(BaseModel):
    quiz_id: str
    answers: List[int] = Field(..., description="0-based option index for each question")
    time_taken: int = Field(..., description="Seconds taken to complete the quiz")


class QuizSessionResult(BaseModel):
    quiz_id: str
    score: int
    total: int
    percentage: float
    time_taken: int
    feedback: str
    topic: str
    difficulty: str


# ── Quiz History ───────────────────────────────────────────────────────────


class QuizHistoryItem(BaseModel):
    quiz_id: str
    topic: str
    difficulty: str
    score: int
    total: int
    percentage: float
    time_taken: int
    taken_at: str


class QuizHistory(BaseModel):
    sessions: List[QuizHistoryItem]
    total_sessions: int


# ── Learner Profile ────────────────────────────────────────────────────────


class TopicMastery(BaseModel):
    topic: str
    mastery_score: float = Field(ge=0, le=100)
    quizzes_taken: int
    avg_score: float
    last_updated: Optional[str] = None


class LearnerProfile(BaseModel):
    user_id: str
    topics: List[TopicMastery]
    overall_mastery: float
    total_quizzes: int


class LearnerUpdateRequest(BaseModel):
    topic: str
    mastery_score: float = Field(..., ge=0, le=100)
