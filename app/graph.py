"""
Builds the LangGraph state machine and exposes run_agent() as the single
entry point the rest of the app calls. Session history is handled by
MemorySaver, keyed on session_id - good enough for a single-container
Space; if this ever needs to survive a restart or scale to multiple
replicas, swap MemorySaver for a Postgres/Redis checkpointer.
"""

import time

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.nodes import (
    answer_validator_node,
    guardrail_node,
    query_rewriter_node,
    rag_node,
    router_node,
    sql_node,
    synthesis_node,
)
from app.state import AgentState


def route_after_guardrail(state: AgentState) -> str:
    return "end" if state.get("guardrail_triggered") else "continue"


def route_after_router(state: AgentState) -> str:
    return state.get("route", "rag")


builder = StateGraph(AgentState)

builder.add_node("guardrail", guardrail_node)
builder.add_node("rewriter", query_rewriter_node)
builder.add_node("router", router_node)
builder.add_node("rag", rag_node)
builder.add_node("sql", sql_node)
builder.add_node("validator", answer_validator_node)
builder.add_node("synthesis", synthesis_node)

builder.set_entry_point("guardrail")

builder.add_conditional_edges(
    "guardrail", route_after_guardrail, {"end": END, "continue": "rewriter"}
)
builder.add_edge("rewriter", "router")
builder.add_conditional_edges(
    "router",
    route_after_router,
    {"rag": "rag", "sql": "sql", "both": "rag", "out_of_scope": END},  # "both" runs RAG first, then SQL
)
builder.add_conditional_edges(
    "rag",
    lambda state: "sql" if state.get("route") == "both" else "validate",
    {"sql": "sql", "validate": "validator"},
)
builder.add_edge("sql", "validator")
builder.add_edge("validator", "synthesis")
builder.add_edge("synthesis", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
print("Graph compiled.")


def run_agent(query: str, session_id: str = "default") -> dict:
    start = time.time()
    config = {"configurable": {"thread_id": session_id}}

    # pull existing history for this session so multi-turn context carries over
    existing_state = graph.get_state(config)
    existing_history = []
    if existing_state and existing_state.values:
        existing_history = existing_state.values.get("chat_history", [])

    initial_state = {
        "query": query,
        "rewritten_query": "",
        "route": "rag",
        "rag_chunks": [],
        "rag_answer": "",
        "rag_citations": [],
        "sql_query": "",
        "sql_dataframe": "",
        "sql_answer": "",
        "sql_corrections": 0,
        "sql_error": "",
        "final_answer": "",
        "chat_history": existing_history + [{"role": "user", "content": query}],
        "latency_ms": 0.0,
        "guardrail_triggered": False,
    }

    result = graph.invoke(initial_state, config=config)
    elapsed = (time.time() - start) * 1000

    graph.update_state(
        config, {"chat_history": [{"role": "assistant", "content": result["final_answer"]}]}
    )

    return {
        "answer": result["final_answer"],
        "route": result.get("route"),
        "citations": result.get("rag_citations", []),
        "sql_used": result.get("sql_query", ""),
        "sql_corrections": result.get("sql_corrections", 0),
        "latency_ms": round(elapsed, 1),
        "guardrail_hit": result.get("guardrail_triggered", False),
    }

