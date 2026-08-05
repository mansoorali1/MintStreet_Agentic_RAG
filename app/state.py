"""
The shared state object that flows through every node in the LangGraph
agent. Each node reads what it needs off this and writes its own results
back onto it - nothing is passed around as separate function arguments.
"""

import operator
from typing import Annotated, Literal, TypedDict


class AgentState(TypedDict):
    query: str
    # follow-up questions get rewritten into a self-contained form here,
    # e.g. "compare with last year" -> "compare UPI volume 2023-24 vs 2022-23"
    rewritten_query: str
    route: Literal["rag", "sql", "both", "out_of_scope"]

    # RAG branch outputs
    rag_chunks: list
    rag_answer: str
    rag_citations: list

    # SQL branch outputs
    sql_query: str
    sql_dataframe: str  # stored as a JSON string, TypedDict can't hold a DataFrame
    sql_answer: str
    sql_corrections: int
    sql_error: str

    final_answer: str

    # LangGraph's checkpointer persists this across turns for a session,
    # we also keep it here so it's easy to pass straight into Groq calls
    chat_history: Annotated[list, operator.add]

    latency_ms: float
    guardrail_triggered: bool

