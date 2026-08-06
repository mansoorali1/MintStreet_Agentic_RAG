# MintStreet — Agentic RAG

An enterprise-grade **Agentic RAG and Text-to-SQL system** designed to answer complex, multi-modal questions over 10 years of **Reserve Bank of India (RBI) Annual Reports** and granular digital payments datasets (UPI, NEFT, RTGS, Cards, and ATMs).

Built with **LangGraph**, **Pinecone**, **Supabase/PostgreSQL**, and **Groq LLMs**, MintStreet dynamically routes questions across qualitative textual policy analysis, structured relational SQL analytics, or hybrid dual-engine synthesis with strict answer grounding.

---

## Architecture

```text
User Query
    │
    ▼
Guardrail  ──(out of scope)──▶  Polite Decline
    │
    ▼
Query Rewriter (resolves follow-ups using chat memory)
    │
    ▼
Router  ──▶  rag  |  sql  |  both
    │              │         │
    ▼              ▼         ▼
  RAG Node      SQL Node   RAG Node → SQL Node
  (hybrid          (text-to-SQL
   search +         with retry loop)
   rerank)
    │              │         │
    └──────┬───────┴─────────┘
           ▼
     Answer Validator
           ▼
      Synthesis (merge + grounding check for "both" route)
           ▼
     Final Answer
```

### Retrieval & Pipeline Mechanics
* **Multi-Modal Document Ingestion:** Uses Docling to parse dense RBI Annual Report PDFs, converting complex financial tables to Markdown format and generating Vision-LLM annotations for embedded charts.
* **Hybrid Retrieval (Dense + Sparse):** Combines dense vector retrieval (Pinecone with `all-MiniLM-L6-v2`) with sparse lexical search (BM25). Merges results via Reciprocal Rank Fusion (RRF) and reranks top candidates using a Cross-Encoder (`ms-marco-MiniLM-L-6-v2`).
* **Self-Correcting Text-to-SQL:** Translates natural language questions into PostgreSQL queries against digital payments database on Supabase. Implements an automated feedback loop with up to 3 retries using dynamic schema descriptions and runtime error tracebacks.
* **Dual-Engine Fusing & Grounding:** For complex hybrid queries requiring both policy text and quantitative metrics, outputs from RAG and SQL are merged by an LLM synthesis step, followed by an automated validation pass to strip ungrounded metrics.

---

## Project Structure

```text
MintStreet-Agentic-RAG/
├── app/                  # Application package — config, clients, retrieval, graph, UI
├── ingestion/            # Offline pipeline building Pinecone index & local artifacts
├── artifacts/            # Pre-built BM25 index, chunk metadata, column mappings
├── notebooks/            # System evaluation, ablation study, and ingestion notebooks
├── main.py               # Container entrypoint / application server
├── Dockerfile            # Container build specification
├── requirements.txt      # Project dependencies
└── README.md             # Project documentation
```

---

## Tech Stack

* **Orchestration & Graph:** LangGraph, LangChain
* **LLMs & Inference:** Groq API (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`)
* **Vector Store & Retrieval:** Pinecone, BM25 (`rank_bm25`), Cross-Encoders (`sentence-transformers`)
* **Database & Storage:** PostgreSQL / Supabase, SQLAlchemy
* **Parsing & Extraction:** Docling, Vision Models
* **Evaluation Framework:** RAGAS Benchmark
* **Deployment & UI:** Gradio, Docker, GitHub Actions, Render / Hugging Face Spaces

---

## Local Development Setup

### Prerequisites
* Python 3.10+
* PostgreSQL / Supabase instance
* Pinecone API key
* Groq API key

### Quickstart

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/MintStreet-Agentic-RAG.git
   cd MintStreet-Agentic-RAG
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Add your API keys (`GROQ_API_KEY`, `PINECONE_API_KEY`, `SUPABASE_DB_URL`) to `.env`.

3. **Install dependencies and launch:**
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

---

## Deployment & CI/CD

This repository includes a continuous integration and continuous deployment (CI/CD) workflow configured via **GitHub Actions** and **Docker**:

1. On every push to `main`, GitHub Actions executes syntax checks and compilation gates.
2. Upon passing, a trigger calls the Render / Hugging Face Deploy Hook to pull the latest image and deploy zero-downtime updates.

---

## Evaluation

The retrieval pipeline and graph execution were evaluated using **RAGAS** against a benchmark of hand-crafted QA pairs covering RAG, Text-to-SQL, hybrid synthesis, and multi-turn follow-up queries. Ablation studies were conducted across multiple architectural configurations to validate routing precision and contextual faithfulness.
