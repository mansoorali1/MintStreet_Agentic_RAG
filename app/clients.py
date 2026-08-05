"""
Every external client and pre-built artifact the app depends on, set up once
at import time.

This runs a single time when the container starts (Gradio holds one process
per Space), not per-request, so loading the embedder/reranker/BM25 index
here rather than inside a request handler is what keeps response times sane.
"""

import json
import os
import pickle

import sqlalchemy
from groq import Groq
from pinecone import Pinecone
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.config import (
    ARTIFACTS_DIR,
    GROQ_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX,
    SUPABASE_DB_URL,
)

# --- API clients -------------------------------------------------------

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

groq = Groq(api_key=GROQ_API_KEY)

engine = sqlalchemy.create_engine(SUPABASE_DB_URL)

# --- Local models --------------------------------------------------------
# these get downloaded from HF on first container build and then cached
# in the image layer, so cold starts after that are fast

embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# --- Pre-built retrieval artifacts ---------------------------------------
# these are produced by ingestion/build_pinecone_index.py and committed
# straight into artifacts/, see the ingestion script for how they're made

with open(os.path.join(ARTIFACTS_DIR, "bm25_index.pkl"), "rb") as f:
    bm25 = pickle.load(f)

with open(os.path.join(ARTIFACTS_DIR, "chunks_metadata.pkl"), "rb") as f:
    all_chunks = pickle.load(f)

with open(os.path.join(ARTIFACTS_DIR, "column_mapping.json"), "r") as f:
    column_mapping = json.load(f)

# inverse maps: DB column name -> human readable label, used when we show
# query results back to the LLM/user instead of raw snake_case columns
yearly_inv = {v: k for k, v in column_mapping["digital_payments_yearly"].items()}
monthly_inv = {v: k for k, v in column_mapping["digital_payments_monthly"].items()}

print("Clients and artifacts loaded.")

