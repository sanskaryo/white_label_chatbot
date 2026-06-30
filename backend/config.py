# WHAT DOES THIS FILE DO: loads all env config values for the white-label chatbot

# ================== IMPORTS ==================
import os
from pathlib import Path

from dotenv import load_dotenv
# ================== IMPORTS ==================


load_dotenv(override=True)


# =========== VARIABLES : Azure OpenAI credentials ===========
FOUNDRY_ENDPOINT = os.getenv("FOUNDRY_ENDPOINT", "")
FOUNDRY_API_KEY = os.getenv("FOUNDRY_API_KEY") or os.getenv("azure_deploy", "")
FOUNDRY_DEPLOYMENT = os.getenv("FOUNDRY_DEPLOYMENT", "")
AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL", "text-embedding-3-large")
# =========== VARIABLES : Azure OpenAI credentials ===========


# =========== VARIABLES : RAG retrieval and reranker tuning ===========
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "1500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))

CORRECTION_MATCH_THRESHOLD = float(os.getenv("CORRECTION_MATCH_THRESHOLD", "0.90"))

RERANK_SKIP_TOP1 = float(os.getenv("RERANK_SKIP_TOP1", "0.72"))
RERANK_SKIP_GAP = float(os.getenv("RERANK_SKIP_GAP", "0.06"))
ENABLE_RERANKING = os.getenv("ENABLE_RERANKING", "true").lower() in ("1", "true", "yes", "y")

HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.55"))
HYBRID_BM25_WEIGHT = float(os.getenv("HYBRID_BM25_WEIGHT", "0.45"))
# =========== VARIABLES : RAG retrieval and reranker tuning ===========


# =========== VARIABLES : LLM output limit and data file paths ===========
MAX_COMPLETION_TOKENS = int(os.getenv("MAX_COMPLETION_TOKENS", "600"))

# White-label: no hardcoded data files — data comes only from user uploads
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".")).resolve()
RESPONSE_CACHE_FILE = Path("response_cache.json")
# =========== VARIABLES : LLM output limit and data file paths ===========


# =========== VARIABLES : embedding and response cache settings ===========
EMBED_CACHE_VERSION = 2

FILE_CACHE_TTL_SEC = int(os.getenv("FILE_CACHE_TTL_SEC", str(24 * 3600)))

# question response cache settings (Upstash Redis)
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
REDIS_RESPONSE_CACHE_TTL = int(os.getenv("REDIS_RESPONSE_CACHE_TTL", "21600"))  # seconds, 0 = never expire
CACHE_MIN_HITS = int(os.getenv("CACHE_MIN_HITS", "5"))                          # RAG hits before promoting to cache
CACHE_FUZZY_THRESHOLD = float(os.getenv("CACHE_FUZZY_THRESHOLD", "0.97"))       # higher than corrections (0.90) — near-identical only

QUERY_EMBED_CACHE_SIZE = max(
    0,
    int(os.getenv("QUERY_EMBED_CACHE_SIZE", "512"))
)

QUERY_EMBED_CACHE_TTL_SEC = max(
    0.0,
    float(os.getenv("QUERY_EMBED_CACHE_TTL_SEC", "3600"))
)
# =========== VARIABLES : embedding and response cache settings ===========


# =========== VARIABLES : server limits and security settings ===========
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
UPLOAD_MAX_FILE_SIZE_MB = int(os.getenv("UPLOAD_MAX_FILE_SIZE_MB", "50"))
UPLOAD_MAX_FILE_SIZE_BYTES = UPLOAD_MAX_FILE_SIZE_MB * 1024 * 1024
UPLOADER_SECRET = os.getenv("UPLOADER_SECRET", "").strip()

TRUSTED_PROXY = os.getenv("TRUSTED_PROXY", "0").lower() in ("1", "true", "yes", "y")
RAW_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").strip()
ALLOWED_ORIGINS = [o.strip() for o in RAW_ALLOWED_ORIGINS.split(",") if o.strip()] if RAW_ALLOWED_ORIGINS != "*" else ["*"]

DISABLE_RATE_LIMIT = os.getenv("DISABLE_RATE_LIMIT", "").strip().lower() in ("1", "true", "yes", "y")
RATE_LIMIT_CALLS = int(os.getenv("RATE_LIMIT_CALLS", "10"))
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "60"))

INCLUDE_TIMINGS = os.getenv("INCLUDE_TIMINGS", "1").strip().lower() in ("1", "true", "yes", "y")
# =========== VARIABLES : server limits and security settings ===========


# =========== VARIABLES : pgvector and Supabase storage configuration ===========
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
PGVECTOR_ENABLED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)

SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "chatbot-uploads").strip()
# =========== VARIABLES : pgvector and Supabase storage configuration ===========


# =========== VARIABLES : White-label bot identity ===========
BOT_NAME = os.getenv("BOT_NAME", "Assistant")
BOT_DESCRIPTION = os.getenv("BOT_DESCRIPTION", "AI-powered knowledge assistant")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip()
# =========== VARIABLES : White-label bot identity ===========


# =========== VARIABLES : Langfuse LLM observability ===========
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
LANGFUSE_LOG_PROMPTS = os.getenv("LANGFUSE_LOG_PROMPTS", "true").lower() in ("1", "true", "yes", "y")
LANGFUSE_ENABLED = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
# =========== VARIABLES : Langfuse LLM observability ===========
