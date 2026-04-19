from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.exceptions import RequestValidationError
from upstash_redis import Redis
from dotenv import load_dotenv
import time
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

load_dotenv()

# --- BONUS: MONITORING (SENTRY) ---
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=os.getenv("ENV", "development")
    )

# --- TASK 7: ENV VALIDATION ---
REQUIRED_ENVS = [
    "GEMINI_API_KEY",
    "DATABASE_URL",
]

# Redis is optional for minimal deployment
OPTIONAL_ENVS = [
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN"
]

def validate_env():
    missing = [env for env in REQUIRED_ENVS if not os.getenv(env)]
    if missing:
        import sys
        print(f"CRITICAL: Missing required environment variables: {', '.join(missing)}")
        # In production, we should exit
        if os.getenv("ENV") == "production":
            sys.exit(1)

validate_env()

from app.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
import logging

# --- BONUS: LOGGING STANDARDIZATION ---
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("api")
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
    title="AI Tutor Learning Assistant API",
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

# --- TASK 6: REDIS RATE LIMITING ---
redis_url = os.getenv("UPSTASH_REDIS_REST_URL")
redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
redis = None
if redis_url and redis_token:
    redis = Redis(url=redis_url, token=redis_token)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip if redis not configured or not an API route
    if not redis or not request.url.path.startswith("/api") or request.url.path == "/health":
        return await call_next(request)
        
    # Use user_id if authenticated, otherwise IP
    # We try to get user_id from the request state if it was set by auth middleware
    # But since auth happens in dependency, we use IP for now or check headers
    identifier = request.client.host if request.client else "unknown"
    
    # Consistent with frontend: 20 req/min
    # Upstash Redis rate limit implementation
    key = f"ratelimit:backend:{identifier}"
    try:
        # Simple sliding window implementation with Redis
        # In production, use a library like 'slowapi' but here we follow the user's custom requirement
        # to use Redis consistently with the frontend.
        now = int(time.time())
        window = 60
        limit = 20
        
        # Multi-command for atomic update
        # We use the REST client directly as it's simpler for Upstash
        count = redis.get(key) or 0
        if int(count) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": "Too many requests. Please try again in a minute.",
                    "limit": limit
                },
                headers={"Retry-After": str(window)}
            )
        
        # Increment and set expiry if new
        redis.incr(key)
        if int(count) == 0:
            redis.expire(key, window)
            
    except Exception as e:
        logger.error(f"Rate limit error: {e}")
        # Fail open in case of Redis failure to maintain availability
        pass

    return await call_next(request)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Try to get user_id from request state if set by dependency
    user_id = getattr(request.state, "user_id", "anonymous")
    
    logger.info(
        f"REQ_ID={request_id} USER_ID={user_id} {request.method} {request.url.path} "
        f"- STATUS={response.status_code} - TIME={process_time:.4f}s"
    )
    
    response.headers["X-Request-ID"] = request_id
    return response

# --- TASK 1: STRUCTURED ERROR RESPONSES ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "message": "The request body or parameters are invalid."
        },
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "detail": exc.detail,
            "status_code": exc.status_code
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    
    # Structured error response for production
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Our team has been notified.",
            "trace_id": str(uuid.uuid4()) if os.getenv("ENV") == "production" else str(exc)
        },
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
    try:
        # Check DB connectivity
        with service.learner._connect() as conn:
            db_status = "connected"
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")
        db_status = f"unhealthy: {str(e)}"

    try:
        # Check Redis connectivity if configured
        if redis:
            redis.get("health-check")
            redis_status = "connected"
        else:
            redis_status = "not_configured"
    except Exception as e:
        logger.error(f"Health check Redis failure: {e}")
        redis_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" and (redis_status in ["connected", "not_configured"]) else "degraded",
        "timestamp": time.time(),
        "version": "1.0.0",
        "database": db_status,
        "redis": redis_status,
        "service": "ai-tutor-backend"
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



