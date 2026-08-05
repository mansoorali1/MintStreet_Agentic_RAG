"""
Every node in the LangGraph pipeline. Each function takes the current
AgentState and returns a partial dict that gets merged back into it -
that's the LangGraph node contract, nothing fancier going on.

Flow: guardrail -> rewriter -> router -> (rag and/or sql) -> validator -> synthesis
See graph.py for how these get wired together.
"""

import numpy as np
import pandas as pd

from app.clients import monthly_inv, yearly_inv
from app.config import GROQ_ROUTING_MODEL
from app.llm import call_groq
from app.retrieval import hybrid_search
from app.schema import SCHEMA_DESCRIPTION  # noqa: F401  (imported for clarity/future use)
from app.sql_engine import run_sql_with_retry
from app.state import AgentState


def guardrail_node(state: AgentState) -> dict:
    """Keeps the assistant on-topic. Skips the check for short follow-up
    style messages once a conversation is already underway - re-checking
    "what about monthly?" against the topic classifier is wasted latency
    and occasionally misfires on short fragments."""
    query = state["query"]
    chat_history = state.get("chat_history", [])

    if len(chat_history) > 1:
        vague_followups = ["same", "that", "it", "this", "again",
                            "monthly", "yearly", "show me", "what about", "previous"]
        # only skip the check if it's short AND has a real reference word -
        # a long fully-formed new question shouldn't get a free pass just
        # because it happens to contain "and"
        if len(query.split()) <= 8 and any(sig in query.lower() for sig in vague_followups):
            return {"guardrail_triggered": False}

    prompt = f"""Is this question related to any of these topics:
- RBI (Reserve Bank of India) annual reports or policies
- Indian digital payments (UPI, NEFT, RTGS, IMPS, cards, mobile payments)
- Indian banking system, financial regulation, monetary policy
- Payment infrastructure in India (ATMs, POS terminals, QR codes)
Question: "{query}"
Reply with only YES or NO."""

    result = call_groq(
        [{"role": "user", "content": prompt}],
        model=GROQ_ROUTING_MODEL,
        temperature=0.0,
        max_tokens=200,           # room for hidden reasoning tokens, not just the YES/NO
        reasoning_effort="low",
        reasoning_format="hidden",
    )
    result_clean = result.strip().upper()

    if result_clean not in ("YES", "NO"):
        # fail open rather than closed - a parsing hiccup shouldn't block a real question
        triggered = False
    else:
        triggered = result_clean != "YES"

    if triggered:
        return {
            "guardrail_triggered": True,
            "final_answer": (
                "I'm built to answer questions about RBI Annual Reports and "
                "India's digital payment systems. I can help with topics like "
                "UPI growth, payment trends, RBI policy, banking regulation, "
                "and related data. Could you ask something along those lines?"
            ),
            "route": "out_of_scope",
        }
    return {"guardrail_triggered": False}


def query_rewriter_node(state: AgentState) -> dict:
    """Resolves follow-up references using chat history.
    'compare with last year' -> 'compare UPI volume in 2023-24 with 2022-23'
    If there's no history, or the query is already self-contained, it's
    returned unchanged - no point spending a call on a fresh question."""
    query = state["query"]
    chat_history = state.get("chat_history", [])

    if not chat_history:
        return {"rewritten_query": query}

    vague_signals = ["that", "it", "this", "again", "same", "previous",
                      "last year", "compare", "more detail", "explain again",
                      "simpler", "elaborate"]
    needs_rewrite = any(sig in query.lower() for sig in vague_signals)
    if not needs_rewrite:
        return {"rewritten_query": query}

    recent = chat_history[-4:]  # last 2 turns
    history_str = "\n".join(f"{m['role'].upper()}: {m['content'][:300]}" for m in recent)
    prompt = f"""Given this conversation history:
{history_str}
Rewrite this follow-up question as a fully self-contained question with no pronouns or references:
Follow-up: "{query}"
Return only the rewritten question, nothing else."""

    rewritten = call_groq(
        [{"role": "user", "content": prompt}],
        model=GROQ_ROUTING_MODEL,
        temperature=0.0,
        max_tokens=150,
    )
    return {"rewritten_query": rewritten}


def router_node(state: AgentState) -> dict:
    """Decides whether this needs the PDF text (rag), the payments
    database (sql), or both. Also catches questions that ask for numbers
    we simply don't have (e.g. NPA ratios) and sends those to RAG only,
    with a note attached instead of pretending SQL can answer them."""
    query = state.get("rewritten_query") or state["query"]
    prompt = f"""Classify this question for a financial intelligence system about RBI and Indian payments.
The system has:
1. RBI Annual Report PDFs (text, policy, qualitative analysis - ALL chapters, not just payments)
2. Payment systems database (UPI, NEFT, RTGS, cards, ATMs, mobile payments numbers ONLY)
Classify into exactly one:
- "rag" -> needs text from PDF only (policy questions, explanations, qualitative)
- "sql" -> needs numbers from payment database only (UPI stats, card transaction counts, ATM data)
- "both" -> needs both text context AND payment numbers together
- "sql_unavailable" -> asks for numbers but topic is NOT in payment database (e.g. bank credit, NPA ratios, gold loans, MSME data)
Question: "{query}"
Reply with only one word: rag / sql / both / sql_unavailable"""

    result = call_groq(
        [{"role": "user", "content": prompt}],
        model=GROQ_ROUTING_MODEL,
        temperature=0.0,
        max_tokens=200,
        reasoning_effort="low",
        reasoning_format="hidden",
    )
    raw_route = result.strip().lower()

    if raw_route == "sql_unavailable":
        return {
            "route": "rag",
            "sql_error": (
                "The specific numerical data requested is not available in the "
                "payment systems database, which covers UPI, NEFT, cards, and ATM data only. "
                "Showing qualitative information from the RBI Annual Reports instead."
            ),
        }

    route = raw_route if raw_route in ("rag", "sql", "both") else "rag"
    return {"route": route}


RAG_SYSTEM_PROMPT = """You are a financial analyst assistant for RBI Annual Reports and Indian payments.
Answer using ONLY the provided context. If context is insufficient, say so clearly.
Be precise with numbers - quote them exactly as they appear in the context.
Answer only what the user asked. Do not add extra sections, unrelated tables,
or additional summaries that were not requested.
Synthesize and paraphrase the context into your own well-organized answer. Do NOT
insert inline citation markers like [Source 1] or 【Source 1】 anywhere in your text -
citations are handled separately by the application and must not appear anywhere in
your response, inline or otherwise.
If there are many relevant points, prioritize the most important ones and organize them
clearly (e.g. with short headers or bullets) rather than listing every excerpt verbatim.
Do NOT include a sources, citations, or references section of any kind at the
end of your answer.
Answer in the minimum length needed to fully address the question - do not pad for
thoroughness. Use a table only when comparing 3+ numeric rows. Use at most one level
of bullets (no nested sub-bullets) unless the question explicitly asks for a breakdown.
Do not add a "Together/In summary/Overall" concluding paragraph unless the user asked
for a summary. Do not restate the question at the start of your answer.
When many items are available, present only the most important or representative ones
in the initial response. Avoid exhaustive lists unless the user explicitly requests them.
If more relevant items exist, briefly note that additional detail is available on request.
Infer the expected answer shape from how the question is phrased: a direct factual
question wants a short direct answer; "list/what are the" wants concise bullets;
"compare" wants a table; "explain/why/how" wants a short paragraph explanation. Use this
as a guide for shape, not a rigid rule - prioritize matching what the user actually
seems to want over any single trigger word.
If you know a fact from general/training knowledge that is not present in the provided
context, do NOT include it, even to "update" or "complete" a fact that is in the context.
State only what the context supports, even if you believe it may be outdated.
If the question asks for specific statistics, percentages, or transaction figures that
are not present anywhere in the provided context, do not estimate, recall, or guess
them from general knowledge - simply do not address that part of the question. A separate
system handles numerical/database queries; your job is only the qualitative context above."""


def rag_node(state: AgentState) -> dict:
    """Runs hybrid search + reranker, then generates an answer grounded
    strictly in the retrieved chunks."""
    query = state.get("rewritten_query") or state["query"]
    chat_history = state.get("chat_history", [])
    chunks = hybrid_search(query)

    context_parts = []
    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        context_parts.append(
            f"[Source {i+1}: {meta.get('source_file','')}, "
            f"Year: {meta.get('year','')}, Page: {meta.get('page_num','')}]\n"
            f"{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    messages = []
    if chat_history:
        messages.extend(chat_history[-6:])
    messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"})

    answer = call_groq(
        [{"role": "system", "content": RAG_SYSTEM_PROMPT}] + messages,
        temperature=0.0,
        max_tokens=2000,
    )

    citations = [
        {
            "source": c["metadata"].get("source_file", ""),
            "year": c["metadata"].get("year", ""),
            "page": c["metadata"].get("page_num", ""),
            "chapter": c["metadata"].get("chapter", ""),
            "chunk_type": c["metadata"].get("chunk_type", "text"),
        }
        for c in chunks
    ]
    return {"rag_chunks": chunks, "rag_answer": answer, "rag_citations": citations}


SQL_ANALYST_SYSTEM_PROMPT = """You are a financial analyst. Convert these query results into a clear, insightful answer.
UNIT CONVERSION - follow this exactly:
- Volume columns end in _vol, data is in LAKHS (1 lakh = 100,000)
- Value columns end in _val, data is in CRORES (1 crore = 10 million rupees)
- Convert lakhs to billions by dividing by 10,000, and crores to trillion rupees by dividing by 100,000, before writing your answer
- State ONLY the final converted number (e.g. "45.96 billion transactions"). Do NOT show the raw lakh/crore figure, the division, or any arithmetic anywhere in your answer - the conversion must happen silently in your reasoning, not in the response text
- Never say "million transactions" for UPI - volumes are in billions range post-2019
- Write your answer as a complete, natural sentence (e.g. "In FY2022, UPI processed approximately 45.96 billion transactions"). Do NOT show the raw lakh/crore figure, the division you performed, or any arithmetic anywhere in your answer - only the final converted number should appear, embedded naturally in the sentence.
Include CAGR if time series. Don't mention SQL or databases - just present the findings naturally.
Answer in the minimum length needed to fully address the question - do not pad for
thoroughness. Use a table only when comparing 3+ numeric rows. Use at most one level
of bullets (no nested sub-bullets) unless the question explicitly asks for a breakdown.
Do not add a "Together/In summary/Overall" concluding paragraph unless the user asked
for a summary. Do not restate the question at the start of your answer.
Only answer the part of the question that this data actually supports. If the question
has other parts not covered by the data below (e.g. policy changes, regulations, qualitative
context), ignore those parts entirely - do not answer them from general knowledge or training
data, do not guess, and do not mention anything not present in the data below.
When many rows are available, present only the most important or representative ones in
the initial response. Avoid exhaustive lists unless the user explicitly requests them.
If more relevant rows exist, briefly note that additional detail is available on request."""


def sql_node(state: AgentState) -> dict:
    """Runs text-to-SQL with the retry loop, renames columns to readable
    labels, computes CAGR for time series, and hands it all to the LLM
    for a natural-language answer."""
    query = state.get("rewritten_query") or state["query"]

    df, sql, corrections, error = run_sql_with_retry(query)
    if error:
        return {
            "sql_query": sql,
            "sql_dataframe": "",
            "sql_answer": "",
            "sql_corrections": corrections,
            "sql_error": error,
        }

    inv_map = yearly_inv if "yearly" in sql.lower() else monthly_inv
    df_display = df.rename(columns=lambda c: inv_map.get(c, c))

    # drop internal helper columns that should never reach the LLM/user
    helper_cols = {"fiscal_year_start_int", inv_map.get("fiscal_year_start_int", "")}
    df_display = df_display.drop(columns=[c for c in helper_cols if c in df_display.columns], errors="ignore")

    # reformat date columns to "Month Year" text so the LLM never states
    # a fake day-of-month (month_year is stored as the 1st of the month)
    for col in df_display.columns:
        if pd.api.types.is_datetime64_any_dtype(df_display[col]) or \
           df_display[col].apply(lambda x: hasattr(x, "strftime")).any():
            df_display[col] = pd.to_datetime(df_display[col]).dt.strftime("%B %Y")

    df_string = df_display.to_string(index=False)
    sql_table_md = df_display.to_markdown(index=False)

    # compute CAGR when we have a real multi-row time series
    cagr_note = ""
    if len(df) > 2:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        value_cols = [c for c in numeric_cols if "year" not in c.lower()]
        if value_cols:
            col = value_cols[0]
            try:
                first = df[col].dropna().iloc[0]
                last = df[col].dropna().iloc[-1]
                n = len(df[col].dropna()) - 1
                if first > 0 and last > 0 and n > 0:
                    cagr = ((last / first) ** (1 / n) - 1) * 100
                    readable = inv_map.get(col, col)
                    cagr_note = f"\nCAGR of {readable} over this period: {cagr:.1f}%"
            except Exception:
                pass

    messages = []
    chat_history = state.get("chat_history", [])
    if chat_history:
        messages.extend(chat_history[-6:])
    messages.append({
        "role": "user",
        "content": f"Question: {query}\n\nData:\n{df_string}{cagr_note}\n\nProvide a clear analytical answer.",
    })

    answer = call_groq(
        [{"role": "system", "content": SQL_ANALYST_SYSTEM_PROMPT}] + messages,
        temperature=0.0,
        max_tokens=800,
    )

    return {
        "sql_query": sql,
        "sql_dataframe": df.to_json(date_format="iso"),
        "sql_answer": answer,
        "sql_table_md": sql_table_md,
        "sql_corrections": corrections,
        "sql_error": "",
    }


def answer_validator_node(state: AgentState) -> dict:
    """Lightweight sanity check - did we actually attempt to answer the
    question, or did the model dodge it entirely? Not a full RAGAS eval,
    just a cheap guard before the answer reaches the user. We don't retry
    on failure here (too slow for a chat response) - just log it."""
    query = state.get("rewritten_query") or state["query"]
    route = state.get("route", "rag")
    rag_answer = state.get("rag_answer", "")
    sql_answer = state.get("sql_answer", "")

    answer_to_check = sql_answer if route == "sql" else rag_answer
    if route == "both":
        answer_to_check = f"{rag_answer}\n{sql_answer}"

    if not answer_to_check.strip():
        return {}

    prompt = f"""Does this answer make a reasonable attempt to address the question,
even if it says the information is not available? Reply YES or NO only.

Question: {query}
Answer: {answer_to_check[:500]}"""

    result = call_groq(
        [{"role": "user", "content": prompt}],
        model=GROQ_ROUTING_MODEL,
        temperature=0.0,
        max_tokens=200,
        reasoning_effort="low",
        reasoning_format="hidden",
    )
    is_valid = result.strip().upper() == "YES"
    if not is_valid:
        print(f"[validator] answer may not fully address: '{query[:80]}'")

    return {}


def _merge_hybrid_answer(question: str, rag_answer: str, sql_answer: str, sql_table_md: str = "") -> str:
    """Fuses the RAG and SQL answers into one response instead of just
    stacking them as separate blocks."""
    prompt = f"""Combine these two answers into ONE coherent response to the user's question.

QUALITATIVE ANSWER (from RBI reports): {rag_answer}

QUANTITATIVE ANSWER (from payment systems database): {sql_answer}

Question: {question}

Rules:
- If the quantitative answer contains a specific number that answers part of the question,
  state that number directly and confidently. Do NOT include any sentence saying the
  information "is not available" or "cannot be provided" if the quantitative answer
  actually provides it.
- Do not use section headers like "Payment Systems Data" - integrate everything into
  flowing paragraphs/bullets as one unified answer.
- Do not repeat the same fact twice.
- Keep it concise: state the direct answer in 1-3 sentences first, then supporting detail.
  Do not add a summary/conclusion paragraph at the end unless the question asks for one.
  Answer in the minimum length needed to fully address the question - do not pad for
thoroughness. Use a table only when comparing 3+ numeric rows. Use at most one level
of bullets (no nested sub-bullets) unless the question explicitly asks for a breakdown.
Do not add a "Together/In summary/Overall" concluding paragraph unless the user asked
for a summary. Do not restate the question at the start of your answer.
When many items are available, present only the most important or representative ones
in the initial response. Avoid exhaustive lists unless the user explicitly requests them.
If more relevant items exist, briefly note that additional detail is available on request.
Infer the expected answer shape from how the question is phrased: a direct factual
question wants a short direct answer; "list/what are the" wants concise bullets;
"compare" wants a table; "explain/why/how" wants a short paragraph explanation. Use this
as a guide for shape, not a rigid rule - prioritize matching what the user actually
seems to want over any single trigger word.
- Do not add any fact, figure, or detail that is not present in the QUALITATIVE ANSWER
  or QUANTITATIVE ANSWER above, even if you believe it to be true or more current from
  your own general knowledge. If you are not confident a specific detail came from one
  of the two inputs, leave it out entirely."""

    try:
        return call_groq([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=2000)
    except Exception as e:
        print(f"Hybrid merge failed, falling back to concatenation: {e}")
        return f"{rag_answer}\n\n**Payment Systems Data:**\n{sql_answer}"


def _verify_grounding(final_answer: str, rag_answer: str, sql_answer: str, sql_table_md: str = "") -> str:
    """Last line of defense against hallucinated numbers - strips out any
    figure in the merged answer that can't be traced back to either
    source, rather than trying to guess a correction."""
    prompt = f"""Below is a generated answer, followed by the source materials it must be based on.

GENERATED ANSWER:
{final_answer}

SOURCE 1 (qualitative, from RBI reports): {rag_answer}

SOURCE 2 (quantitative, from database): {sql_answer}
{sql_table_md}

Check every specific number, amount, or figure in the GENERATED ANSWER. If a number does
NOT appear (even approximately, allowing for rounding/unit conversion) in either source
above, rewrite the answer removing that specific claim entirely. Do not replace it with
another number, do not soften it into a hedge - just delete that detail cleanly, keeping
the rest of the answer intact and well-formed. If every number is already grounded,
return the answer completely unchanged. Return ONLY the corrected answer text, nothing else."""
    try:
        return call_groq([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=2000)
    except Exception:
        return final_answer


def synthesis_node(state: AgentState) -> dict:
    """Final assembly step - combines RAG + SQL depending on route, and
    handles every partial-data scenario (one side empty, both empty,
    etc.) instead of assuming both always come back clean."""
    route = state.get("route", "rag")
    question = state.get("rewritten_query") or state.get("query", "")
    rag_answer = state.get("rag_answer", "")
    sql_answer = state.get("sql_answer", "")
    sql_error = state.get("sql_error", "")

    if route == "rag":
        final = rag_answer or (
            "I wasn't able to find relevant information in the RBI Annual Reports for this question."
        )
        if sql_error and "not available in the payment systems database" in sql_error:
            final += f"\n\n*Note: {sql_error}*"

    elif route == "sql":
        final = sql_answer if sql_answer else (
            f"I wasn't able to retrieve that data from the payment systems database. Details: {sql_error}"
        )

    elif route == "both":
        if rag_answer and sql_answer:
            final = _merge_hybrid_answer(question, rag_answer, sql_answer, state.get("sql_table_md", ""))
            final = _verify_grounding(final, rag_answer, sql_answer, state.get("sql_table_md", ""))
        elif rag_answer and not sql_answer:
            final = rag_answer
            if sql_error:
                final += (
                    "\n\n*Note: The specific numerical data isn't available in the "
                    "payment systems database (covers UPI, NEFT, RTGS, cards, ATMs only).*"
                )
        elif sql_answer and not rag_answer:
            final = sql_answer
        else:
            final = (
                "I wasn't able to find relevant information in either the RBI "
                "Annual Reports or the payment systems database for this question."
            )

    else:
        final = state.get("final_answer", "Something went wrong. Please try again.")

    return {"final_answer": final}

