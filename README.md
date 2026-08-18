# MintStreet — Agentic RAG

MintStreet is an agentic Retrieval-Augmented Generation (RAG) system that answers natural-language questions over 10 years of Reserve Bank of India (RBI) Annual Reports. It combines semantic + keyword retrieval, structured SQL querying, and multi-turn conversation handling behind a single LangGraph-orchestrated agent, so a user can ask anything from "What was UPI transaction volume in 2022-23?" (structured data) to "What did the report say about the impact of GST stabilisation on the fiscal deficit?" (unstructured text/tables) in the same conversation.
 
## Why this project exists
 
RBI Annual Reports are long, dense PDFs mixing narrative text, financial tables, and charts/images — the kind of document where naive "chunk and embed" RAG breaks down because:
- Numeric/trend questions ("compare X across years") are better answered by SQL over structured tables than by retrieving text chunks.
- A lot of the signal in these reports lives in tables and images, not prose.
- Real users ask follow-up questions ("and what about the year before?") that need conversation memory and query rewriting, not just single-shot retrieval.
MintStreet is built to handle all three of these realistically, with an agent that decides *how* to answer each query rather than forcing every question through one fixed pipeline.

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

The graph is implemented as a stateful `LangGraph` `StateGraph`, with a single `AgentState` `TypedDict` threading query, route, retrieved chunks, SQL results, citations, and chat history through every node. Conversation memory is handled via LangGraph's checkpointer so multi-turn follow-ups work out of the box.
 
## Data pipeline (ingestion)
 
**Source data:** 10 years of RBI Annual Reports (PDF), containing narrative text, financial/statistical tables, and charts/diagrams.
 
**Extraction:** [Docling](https://github.com/docling-project/docling) is used to parse each report into its structural components — paragraphs, tables, and images — rather than doing raw text extraction, which preserves table structure and layout that would otherwise be lost.
 
**Multimodal normalization to text**, so everything can live in a single vector index:
- **Text** — used as-is, chunked with metadata (source report, year, page number, chunk type).
- **Tables** — converted to Markdown so tabular structure (rows/columns/headers) survives chunking and embedding, instead of collapsing into unstructured text.
- **Images/charts** — sent to a vision-capable LLM to generate a detailed textual description of what the image shows (trends, labels, key figures), which is then treated as a regular text chunk.
**Indexing:**
- All three chunk types (text, table-markdown, image-captions) are embedded with a `sentence-transformers` bi-encoder (`all-MiniLM-L6-v2`) and stored in **Pinecone**, tagged with metadata (report year, page, chunk type) to support year-filtered retrieval.
- A parallel **BM25 index** is built over the same chunks for keyword/lexical retrieval, so hybrid search can combine dense semantic similarity with exact-term matching (important for numeric/proper-noun-heavy financial text).
- Selected structured time-series data (e.g., digital payments volumes/values by year and month) is additionally loaded into a **Postgres (Supabase)** database as relational tables, enabling exact SQL aggregation/comparison queries instead of relying on retrieval for numbers that are better answered by a query.
## Retrieval & agent components
 
- **Hybrid search:** combines Pinecone dense retrieval with BM25 sparse retrieval, with optional year-based metadata filtering parsed out of the query (e.g., "in 2022-23" restricts search to that report).
- **Reranking:** a cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) reranks the merged candidate set before it's passed to the LLM, to improve precision over raw retrieval.
- **Router:** an LLM classifier decides whether a query needs RAG, SQL, or both, based on the query itself and the available SQL schema — with a fallback ("SQL unavailable") that routes numeric-sounding-but-unsupported queries to RAG instead of failing.
- **NL → SQL:** the SQL node generates a query against a documented schema (with explicit rules — e.g., don't sort a "2022-23"-style year column alphabetically, use a companion integer year column instead), executes it, and retries with self-correction on failure.
- **Guardrail:** an early node filters out-of-scope queries (unrelated to RBI reports / digital payments / banking regulation) before any retrieval work is done.
- **Query rewriter:** resolves follow-up queries ("what about the year before that?") into a fully-specified standalone query using chat history, before routing.
- **Answer validator + synthesis:** checks that the generated answer is actually supported by retrieved context/SQL results, then assembles the final response with citations back to the source report, page, and chunk.
## Tech stack
 
| Layer | Tools |
|---|---|
| Document parsing | Docling |
| Vector store | Pinecone |
| Relational store | Postgres (Supabase) |
| Sparse retrieval | BM25 (`rank_bm25`) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM inference | Groq (separate models for routing vs. generation) |
| Orchestration | LangGraph (`StateGraph` + checkpointer for memory) |
| UI | Gradio |
| Eval | RAGAS + custom evaluation harness |
 
## Evaluation approach
 
A custom evaluation set of **70 question–answer pairs** was hand-built to cover the different ways real users would query the system:
- 15 pure RAG questions (answerable from report text/tables/images only)
- 15 pure SQL questions (answerable from structured payments data only)
- 15 hybrid questions (require both RAG and SQL to answer fully)
- 15 multi-turn follow-up questions (test conversation memory and query rewriting)
- 10 edge cases (out-of-scope, ambiguous, or adversarial queries, to test the guardrail)
This set is used two ways in the project: once to score the end-to-end production agent, and once to compare candidate retrieval/routing architecture variants against each other before picking the one that ships. (Evaluation *results* are intentionally omitted from this README — see the evaluation notebooks for methodology and metrics.)

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

## Acknowledgements
 
Built on RBI's publicly published Annual Reports. Not affiliated with or endorsed by the Reserve Bank of India.
