from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import time
load_dotenv()

from app.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from app.debug_log import debug_log
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
from app.services.quiz_engine import QuizEngine
# New modular routers
from app.api.routes import (
    chat_router,
    quiz_router,
    learner_router,
    ingestion_router,
)


def _default_data_dir() -> str:
    return str(Path(__file__).resolve().parents[1] / "data")


def _default_db_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "learner.db")

def _default_upload_dir() -> str:
    return str(Path(__file__).resolve().parents[1] / "uploads")

def _resolve_path(path: str) -> str:
    """Resolve a path relative to the project root if it's not absolute."""
    p = Path(path)
    if p.is_absolute():
        return str(p)
    # Root is one level up from app/ (which is where main.py is, actually app/ is at the same level as data/ in some structures)
    # Looking at the list_dir, backend/ is the root for the backend.
    root = Path(__file__).resolve().parents[1]
    return str((root / p).resolve())


def _hydrate_attachments(raw: list[dict]) -> list[dict]:
    attachments: list[dict] = []
    for item in raw or []:
        file_id = item.get("id")
        record = file_store.get_file(file_id) if file_id else None
        if record:
            parsed = {}
            if record.get("content_type") == "application/pdf":
                parsed = file_parser.parse_pdf(record["path"])
            elif str(record.get("content_type", "")).startswith("image/"):
                parsed = file_parser.parse_image(record["path"])
            elif str(record.get("content_type", "")).startswith("text/"):
                try:
                    with open(record["path"], "r", encoding="utf-8") as f:
                        parsed = {"text": f.read()}
                except Exception:
                    parsed = {"text": ""}
            attachments.append(
                {
                    "id": file_id,
                    "name": record.get("name", "upload"),
                    "text": parsed.get("text", ""),
                }
            )
        else:
            attachments.append(
                {
                    "id": item.get("id", ""),
                    "name": item.get("name", "upload"),
                    "text": item.get("text", ""),
                }
            )
    return attachments

app = FastAPI(
    title="SocratiQ Learning Assistant API",
    version="0.2.0",
    description=(
        "Phase 1-5 implementation: ingestion, graph retrieval, learner model, "
        "Socratic teaching endpoints, and JWT authentication."
    ),
)

# Configure CORS from environment variable or default to localhost
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost")
cors_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 3: Basic Rate Limiting (In-memory)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 60  # requests per minute
request_history: dict[str, list[float]] = {}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Only limit API routes
    if not request.url.path.startswith("/"):
        return await call_next(request)
        
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    # Initialize history for IP
    if client_ip not in request_history:
        request_history[client_ip] = []
        
    # Clean up old requests
    request_history[client_ip] = [
        t for t in request_history[client_ip] 
        if now - t < RATE_LIMIT_WINDOW
    ]
    
    if len(request_history[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)}
        )
        
    request_history[client_ip].append(now)
    return await call_next(request)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Phase 4: Enhanced error logging
    logger.error(f"Global exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )

logger.info("Initializing LearningAssistantService...")
service = LearningAssistantService(
    data_dir=_resolve_path(os.getenv("DATA_DIR", _default_data_dir())),
    db_path=_resolve_path(os.getenv("LEARNER_DB_PATH", _default_db_path())),
)
logger.info("Setting up uploads directory...")
uploads_dir = Path(_resolve_path(os.getenv("UPLOAD_DIR", _default_upload_dir())))
uploads_dir.mkdir(parents=True, exist_ok=True)
logger.info("Initializing FileStore...")
file_store = FileStore(db_path=service.db_path)
file_store.initialize()
logger.info("Initializing MultimodalParser...")
file_parser = MultimodalParser()
logger.info("Initializing YouTubeSearchClient...")
youtube_client = YouTubeSearchClient(api_key=os.getenv("YOUTUBE_API_KEY", ""))

# Production/test robustness: initialize schema + KB immediately.
# This avoids reliance on lifespan startup execution in all test harnesses.
logger.info("Running service.initialize()...")
service.initialize()
logger.info("Service initialized successfully.")

# ── Quiz Engine (shares the knowledge graph with the service) ────────────
quiz_engine = QuizEngine(
    knowledge_graph=service.knowledge_graph, 
    learner=service.learner
)

# ── Operational Endpoints ──────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Liveness/readiness probe for production monitoring."""
    snapshot = service.health_snapshot()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "0.2.1",
        "service": "socratiq-backend",
        **snapshot
    }

@app.get("/api/analytics/summary")
async def get_analytics_summary(current: dict = Depends(get_current_user)):
    """
    Protected endpoint for product operators to view usage metrics.
    In a real-world scenario, this would be restricted to admin roles.
    """
    # For now, we aggregate from the learner tracker
    try:
        # We need a small helper in the learner tracker for this
        summary = service.learner.get_system_wide_stats()
        return {
            "status": "success",
            "data": summary
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to fetch analytics: {e}")
        raise HTTPException(status_code=500, detail="Analytics retrieval failed")

@app.get("/api/analytics/user/{user_id}")
async def get_user_analytics(user_id: str, current: dict = Depends(get_current_user)):
    """Compute learning insights for a specific user (Phase 3)."""
    # Authorization check: only allow users to see their own analytics
    if current["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own analytics.")
    
    try:
        analytics = service.learner.get_user_analytics(user_id)
        return {
            "status": "success",
            "data": analytics
        }
    except Exception as e:
        logger.error(f"Failed to fetch user analytics: {e}")
        raise HTTPException(status_code=500, detail="User analytics retrieval failed")

@app.post("/api/feedback")
async def submit_feedback(data: dict, current: dict = Depends(get_current_user)):
    """Collect real user feedback (Phase 2)."""
    user_id = current.get("user_id")
    feedback_text = data.get("feedback")
    rating = data.get("rating")
    
    import logging
    logging.getLogger(__name__).info(f"USER_FEEDBACK: user={user_id} rating={rating} text='{feedback_text}'")
    
    # Store in DB
    service.learner.record_feedback(user_id, feedback_text, rating)
    
    return {"status": "success", "message": "Feedback received. Thank you!"}

# ── Register modular routers ───────────────────────────────────────
app.include_router(chat_router)
app.include_router(quiz_router)
app.include_router(learner_router)
app.include_router(ingestion_router)


@app.on_event("startup")
def on_startup() -> None:
    if getattr(service, "_initialized", False):
        return
    debug_log(
        hypothesisId="A",
        message="startup_init_start",
        data={"data_dir": str(service.data_dir), "db_path": str(service.db_path)},
    )
    service.initialize()
    debug_log(
        hypothesisId="A",
        message="startup_init_done",
        data={"nodes": service.knowledge_graph.graph.number_of_nodes()},
    )


# ──────────────────────────────────────────────────────────
# Auth endpoints
# ──────────────────────────────────────────────────────────
@app.post("/auth/register", response_model=TokenResponse)
def register(body: RegisterRequest) -> TokenResponse:
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Registration failed")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    try:
        user = service.learner.get_user_by_email(body.email)
        if not user or not user.get("password_hash"):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"sub": user["id"], "email": user["email"]})
        
        # Phase 1: Track user login
        service.learner.track_event(
            user_id=user["id"],
            event_type="user_login",
            metadata={"email": user["email"]}
        )

        return TokenResponse(
            access_token=token,
            user_id=user["id"],
            email=user["email"],
            display_name=user.get("display_name", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login failed")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


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



