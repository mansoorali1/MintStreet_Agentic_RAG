"""
Central place for every environment variable the app needs.

On Kaggle these came from UserSecretsClient. In production they come from
whatever injects env vars into the container - GitHub Actions secrets during
CI, and Hugging Face Space secrets at runtime. Reading them all in one file
means if something's missing, the app fails fast at startup instead of
halfway through a user's query.
"""

import os


def _require(name: str) -> str:
    """Fetch an env var or blow up immediately with a useful message.

    Better to fail on container start than 20 minutes in when someone
    finally asks a question that hits the missing key.
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


# Groq (LLM inference)
GROQ_API_KEY = _require("GROQ_API_KEY")
GROQ_GENERATION_MODEL = _require("GROQ_GENERATION_MODEL")
GROQ_ROUTING_MODEL = _require("GROQ_ROUTING_MODEL")

# Pinecone (vector store for PDF chunks)
PINECONE_API_KEY = _require("PINECONE_API_KEY")
PINECONE_INDEX = _require("PINECONE_INDEX")

# Supabase (structured payments data)
SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_KEY = _require("SUPABASE_KEY")
SUPABASE_DB_URL = _require("SUPABASE_DB_URL")

# Local artifacts built during ingestion (see ingestion/build_pinecone_index.py)
ARTIFACTS_DIR = os.environ.get("ARTIFACTS_DIR", "artifacts")

