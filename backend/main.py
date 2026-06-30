# WHAT DOES THIS FILE DO: FastAPI application entry point - wires modular components

# ================== IMPORTS ==================
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import BOT_NAME, BOT_DESCRIPTION, ALLOWED_ORIGINS, CACHE_DIR, PGVECTOR_ENABLED
from core import RAGService, RateLimiter
from core.dependencies import set_service, set_rate_limiter
from utils import setup_logging, log_step
from workflow_db import init_workflow_db, get_active_upload_chunks

import analytics_db   # registers ChatLog with Base before init_workflow_db runs
import sessions_db    # registers VisitorSession with Base before init_workflow_db runs
import cache          # imported here so init_cache() is available after init_workflow_db

from routes import chat, admin, corrections, flagged, blocked_words, uploads, feedback, audit, rbac, departments, users, analytics, activity, sessions, cache_admin, exports
# ================== IMPORTS ==================


# =========== INITIALIZATION ===========
setup_logging()

CACHE_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

init_workflow_db()
cache.init_cache()

service = RAGService()
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

set_service(service)
set_rate_limiter(rate_limiter)

_pgvector_loaded = False
if PGVECTOR_ENABLED:
    with log_step("Load embeddings from Supabase pgvector", emoji="🗄️"):
        _pgvector_loaded = service.load_embeddings_from_pgvector()

if not _pgvector_loaded:
    with log_step("Hydrate uploaded knowledge index", emoji="🗃️"):
        try:
            rows = get_active_upload_chunks(limit=50000)
            if rows:
                docs, embeddings = [], []
                for row in rows:
                    emb = row.get("embedding")
                    txt = (row.get("text") or "").strip()
                    if emb and txt:
                        docs.append({
                            "text": txt, "url": row.get("url") or "",
                            "title": row.get("title") or "Uploaded Knowledge",
                            "category": row.get("category") or "uploaded",
                            "section_type": row.get("section_type") or "uploaded_chunk",
                        })
                        embeddings.append(emb)
                if docs:
                    service.extend_runtime_index(docs, embeddings)
        except Exception as exc:
            print(f"Failed to hydrate uploaded chunks: {exc}")

print(f"{BOT_NAME} backend ready | {len(service.documents)} documents indexed")
# =========== INITIALIZATION ===========


# =========== APP SETUP ===========
app = FastAPI(title=f"{BOT_NAME} - White Label Chatbot", description=BOT_DESCRIPTION, version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

FRONTEND_DIST = Path("frontend/dist")
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

# =========== INCLUDE ROUTERS ===========
app.include_router(chat.router)
app.include_router(rbac.router, prefix="/api/admin/rbac", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(corrections.router, prefix="/api/admin", tags=["admin"])
app.include_router(flagged.router, prefix="/api/admin", tags=["admin"])
app.include_router(blocked_words.router, prefix="/api/admin", tags=["admin"])
app.include_router(uploads.router, prefix="/api/admin", tags=["admin"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
app.include_router(audit.router, prefix="/api/admin", tags=["admin"])
app.include_router(departments.router, prefix="/api/admin", tags=["admin"])
app.include_router(users.router, prefix="/api/admin", tags=["admin"])
app.include_router(analytics.router, prefix="/api/admin", tags=["admin"])
app.include_router(activity.router, prefix="/api/admin", tags=["admin"])
app.include_router(sessions.router, prefix="/api/admin", tags=["admin"])
app.include_router(cache_admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(exports.router, prefix="/api/admin", tags=["admin"])
# =========== INCLUDE ROUTERS ===========

# =========== APP SETUP ===========
