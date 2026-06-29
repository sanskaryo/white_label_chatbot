# WHAT DOES THIS FILE DO: Dependency injection for FastAPI routes

# ================== IMPORTS ==================
from core.rag_service import RAGService
from core.middleware import RateLimiter
# ================== IMPORTS ==================

# Global service instance (initialized in main.py)
_service_instance = None
_rate_limiter_instance = None


def set_service(service: RAGService):
    global _service_instance
    _service_instance = service


def set_rate_limiter(rate_limiter: RateLimiter):
    global _rate_limiter_instance
    _rate_limiter_instance = rate_limiter


def get_service() -> RAGService:
    return _service_instance


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter_instance
