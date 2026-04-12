from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
load_dotenv()

from app.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    FileUploadResponse,
    IngestRequest,
    LoginRequest,
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    YouTubeSearchRequest,
    YouTubeSearchResponse,
)
from app.llm.assistant_service import LearningAssistantService
from app.integrations.multimodal.parser import MultimodalParser
from app.integrations.multimodal.store import FileStore
from app.integrations.youtube.client import YouTubeSearchClient


def _default_data_dir() -> str:
    return str(Path(__file__).resolve().parents[1] / "data")


def _default_db_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "learner.db")

def _default_upload_dir() -> str:
    return str(Path(__file__).resolve().parents[1] / "uploads")

app = FastAPI(
    title="SocratiQ Learning Assistant API",
    version="0.2.0",
    description=(
        "Phase 1-5 implementation: ingestion, graph retrieval, learner model, "
        "Socratic teaching endpoints, and JWT authentication."
    ),
)

# CORS — allow the React frontend in development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = LearningAssistantService(
    data_dir=os.getenv("DATA_DIR", _default_data_dir()),
    db_path=os.getenv("LEARNER_DB_PATH", _default_db_path()),
)
uploads_dir = Path(os.getenv("UPLOAD_DIR", _default_upload_dir()))
uploads_dir.mkdir(parents=True, exist_ok=True)
file_store = FileStore(db_path=os.getenv("LEARNER_DB_PATH", _default_db_path()))
file_store.initialize()
file_parser = MultimodalParser()
youtube_client = YouTubeSearchClient(api_key=os.getenv("YOUTUBE_API_KEY", ""))


@app.on_event("startup")
def on_startup() -> None:
    service.initialize()


# ──────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return service.health_snapshot()


# ──────────────────────────────────────────────────────────
# Auth endpoints
# ──────────────────────────────────────────────────────────
@app.post("/auth/register", response_model=TokenResponse)
def register(body: RegisterRequest) -> TokenResponse:
    existing = service.learner.get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user_id = str(uuid.uuid4())
    hashed = hash_password(body.password)
    user = service.learner.register_user(
        user_id=user_id,
        email=body.email,
        password_hash=hashed,
        display_name=body.display_name or body.email,
    )
    token = create_access_token({"sub": user_id, "email": body.email})
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        email=body.email,
        display_name=user["display_name"],
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    user = service.learner.get_user_by_email(body.email)
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return TokenResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"],
        display_name=user.get("display_name", ""),
    )


@app.get("/auth/me", response_model=UserResponse)
def me(current: dict = Depends(get_current_user)) -> UserResponse:
    user = service.learner.get_user_by_id(current["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        user_id=user["id"],
        email=user.get("email", ""),
        display_name=user.get("display_name", ""),
        created_at=user.get("created_at", ""),
    )


# ──────────────────────────────────────────────────────────
# Knowledge management
# ──────────────────────────────────────────────────────────
@app.post("/ingest")
def ingest(request: IngestRequest, current: dict = Depends(get_current_user)) -> dict:
    result = service.load_knowledge_base(data_dir=request.data_dir)
    return {"status": "ok", **result}


# ──────────────────────────────────────────────────────────
# Chat & Quiz — protected by JWT
# ──────────────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, current: dict = Depends(get_current_user)) -> ChatResponse:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    payload = service.answer_query(
        user_id=current["user_id"],
        query=request.query,
        top_k=request.top_k,
        mode=request.mode,
        attachments=request.attachments,
    )
    return ChatResponse(**payload)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest, current: dict = Depends(get_current_user)) -> StreamingResponse:
    payload = service.answer_query(
        user_id=current["user_id"],
        query=request.query,
        top_k=request.top_k,
        mode=request.mode,
        attachments=request.attachments,
    )
    text = payload.get("result", {}).get("text", "")

    def event_stream():
        for token in text.split(" "):
            yield token + " "

    return StreamingResponse(event_stream(), media_type="text/plain")


@app.post("/quiz/submit", response_model=QuizSubmitResponse)
def submit_quiz(request: QuizSubmitRequest, current: dict = Depends(get_current_user)) -> QuizSubmitResponse:
    payload = service.submit_quiz(
        user_id=current["user_id"],
        node_id=request.node_id,
        question=request.question,
        expected_answer=request.expected_answer,
        user_answer=request.user_answer,
        difficulty=request.difficulty,
    )
    return QuizSubmitResponse(**payload)


@app.post("/quiz/generate", response_model=QuizGenerateResponse)
def generate_quiz(request: QuizGenerateRequest, current: dict = Depends(get_current_user)) -> QuizGenerateResponse:
    attachments = []
    for file_id in request.file_ids:
        record = file_store.get_file(file_id)
        if not record:
            continue
        parsed = {}
        if record.get("content_type") == "application/pdf":
            parsed = file_parser.parse_pdf(record["path"])
        elif str(record.get("content_type", "")).startswith("image/"):
            parsed = file_parser.parse_image(record["path"])
        attachments.append({"id": file_id, "name": record.get("name", ""), "text": parsed.get("text", "")})

    if not attachments:
        raise HTTPException(status_code=400, detail="No valid files for quiz generation")

    text = attachments[0].get("text", "").strip()
    summary = text.split(".")[0][:240] if text else "Review the attached material."
    return QuizGenerateResponse(
        question="Summarize the key concept from your uploaded material.",
        expected_answer=summary or "Review the uploaded material and provide a summary.",
        difficulty="medium",
        citations=[{"heading": attachments[0].get("name", "Uploaded file"), "source": "upload"}],
    )


@app.post("/files/upload", response_model=FileUploadResponse)
def upload_file(file: UploadFile = File(...), current: dict = Depends(get_current_user)) -> FileUploadResponse:
    file_id = str(uuid.uuid4())
    suffix = Path(file.filename).suffix if file.filename else ""
    target_path = uploads_dir / f"{file_id}{suffix}"

    with target_path.open("wb") as handle:
        handle.write(file.file.read())

    size = target_path.stat().st_size
    file_store.add_file(
        file_id=file_id,
        name=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size=size,
        path=str(target_path),
    )

    return FileUploadResponse(
        id=file_id,
        name=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size=size,
    )


@app.post("/search/youtube", response_model=YouTubeSearchResponse)
def search_youtube(request: YouTubeSearchRequest, current: dict = Depends(get_current_user)) -> YouTubeSearchResponse:
    results = youtube_client.search(request.query, max_results=1)
    if not results:
        raise HTTPException(status_code=404, detail="No YouTube results")
    top = results[0]
    return YouTubeSearchResponse(
        title=top.get("title", ""),
        url=top.get("url", ""),
        channel=top.get("channel", ""),
        snippet=top.get("snippet", ""),
    )


@app.get("/learner/progress")
def learner_progress(current: dict = Depends(get_current_user)) -> dict:
    return service.learner_progress(user_id=current["user_id"])
