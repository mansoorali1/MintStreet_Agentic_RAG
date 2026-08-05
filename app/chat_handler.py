"""
The bridge between a Gradio send event and the agent graph. Takes the raw
chat inputs, calls run_agent, and shapes everything the UI needs back out
of it - the answer itself, the trace panel content, and an optional chart.
"""

import tempfile

from app.charts import generate_chart
from app.formatters import (
    build_flowchart_svg,
    format_citations_html,
    format_execution_summary,
    format_generated_query,
    format_route_sources_line,
)
from app.graph import graph, run_agent


def chat(message: str, history: list, session_id: str, trace_badge_count):
    trace_badge_count = int(trace_badge_count)

    if not message.strip():
        return (
            history, "",
            "*Run a query to see execution details.*",
            "*SQL queries will appear here for data questions.*",
            build_flowchart_svg(""), trace_badge_count,
        )

    result = run_agent(message, session_id=session_id)

    answer = result["answer"]
    route = result.get("route", "")
    citations = result.get("citations", [])
    sql_used = result.get("sql_used", "")
    corrections = result.get("sql_corrections", 0)
    latency_ms = result.get("latency_ms", 0)
    guardrail = result.get("guardrail_hit", False)

    exec_summary_md = format_execution_summary(route, latency_ms, guardrail, corrections)
    generated_query_md = format_generated_query(sql_used, corrections)
    flowchart_svg = build_flowchart_svg(active_route=route)
    new_badge_count = trace_badge_count + 1

    # only bother pulling the dataframe back out of graph state and
    # rendering a chart when the route actually produced tabular data
    chart_img = None
    sql_df_json = ""
    if route in ("sql", "both"):
        try:
            config = {"configurable": {"thread_id": session_id}}
            last_state = graph.get_state(config)
            sql_df_json = last_state.values.get("sql_dataframe", "")
        except Exception:
            pass
        if sql_df_json:
            chart_img = generate_chart(sql_df_json, title=message[:60])

    history = history or []
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})

    sources_block = format_route_sources_line(route, citations) + format_citations_html(citations)
    history.append({"role": "assistant", "content": sources_block})

    if chart_img is not None:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        chart_img.save(tmp.name, format="PNG")
        tmp.close()
        history.append({"role": "assistant", "content": (tmp.name,)})

    return (
        history,
        exec_summary_md,
        generated_query_md,
        flowchart_svg,
        new_badge_count,
    )

