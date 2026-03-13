"""Central configuration — loads env vars and defines constants."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from this directory first, then fall back to Backend/.env
_HERE = Path(__file__).resolve().parent
_BACKEND_ENV = _HERE.parent / "Backend" / ".env"

load_dotenv(_HERE / ".env")
load_dotenv(_BACKEND_ENV)

# ── Gemini ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
# Pinned stable production model — do not use preview/latest aliases (#10)
GEMINI_MODEL: str = "gemini-2.5-flash"
# Deterministic inference settings (#2)
GEMINI_TEMPERATURE: float = 0.0
GEMINI_TOP_P: float = 1.0
GEMINI_TOP_K: int = 1
GEMINI_MAX_TOKENS: int = 8192

# ── Supabase ────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

# ── Embedding ───────────────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
EMBEDDING_DIM: int = 384

# ── RAG ─────────────────────────────────────────────────────────────────────
VECTOR_MATCH_THRESHOLD: float = 0.3
VECTOR_MATCH_COUNT: int = 8

# ── Server ──────────────────────────────────────────────────────────────────
PORT: int = int(os.getenv("AI_SERVICE_PORT", "5000"))
