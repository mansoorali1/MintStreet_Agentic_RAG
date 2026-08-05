"""
Pure presentation helpers for the Trace tab - execution summary, the SQL
that was generated, citation lists, and the little routing flowchart.
No business logic lives here, just string/HTML formatting.
"""


def format_route_sources_line(route: str, citations: list) -> str:
    seen, unique = set(), []
    for c in citations:
        key = f"{c.get('source', '')}_{c.get('page', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(c)

    n_sources = len(unique)
    route_label = {
        "rag": "RAG", "sql": "SQL", "both": "Hybrid", "out_of_scope": "Out of Scope",
    }.get(route, route.upper() if route else "—")

    return (
        f'<div style="margin-top:6px;margin-left:4px;margin-bottom:6px;'
        f'color:#6a84a8;font-size:12px;font-family:\'Sora\',sans-serif;">'
        f'Sources: {n_sources} &nbsp;·&nbsp; Route: {route_label}</div>'
    )


def format_citations_html(citations: list) -> str:
    if not citations:
        return ""
    seen, unique = set(), []
    for c in citations:
        key = f"{c.get('source', '')}_{c.get('page', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(c)
    items = "".join(
        f"<li style='margin-bottom: 6px; font-size: 14px; font-weight: 500; color: #e5e7eb;'>"
        f"{c.get('source','').replace('.pdf','').replace('_',' ')} "
        f"<span style='font-size: 12px; font-weight: 400; color: #94a3b8;'>"
        f"(PDF page: {c.get('page','')})</span></li>"
        for c in unique
    )
    sources_list = (
        f"<ul style='margin: 8px 0 0 0; padding-left: 20px; list-style-type: disc;'>{items}</ul>"
    )
    n = len(unique)
    return (
        f"<details>\n"
        f"<summary style='font-size: 14px; font-weight: 500; color: #e2e8f0;'>"
        f"📄 View Sources ({n})</summary>\n\n{sources_list}\n\n</details>"
    )


def format_execution_summary(route: str, latency_ms: float, guardrail_hit: bool, corrections: int) -> str:
    route_display = {
        "rag": "RAG (Document Retrieval)",
        "sql": "SQL (Database Query)",
        "both": "Hybrid (RAG + SQL)",
        "out_of_scope": "Out of Scope",
    }.get(route, route.upper() if route else "—")

    guardrail_display = "⚠️ Triggered" if guardrail_hit else "✅ Passed"
    correction_line = f"\n**SQL Self-corrections:** {corrections}" if corrections > 0 else ""

    return (
        f"**Route:** {route_display}  \n"
        f"**Latency:** {latency_ms}ms  \n"
        f"**Guardrail:** {guardrail_display}"
        f"{correction_line}"
    )


def format_generated_query(sql_used: str, corrections: int) -> str:
    if not sql_used:
        return "*SQL queries will appear here for data questions.*"
    note = f"\n\n*🔄 Self-corrected {corrections} time(s)*" if corrections > 0 else ""
    return f"```sql\n{sql_used}\n```{note}"


def build_flowchart_svg(active_route: str = "") -> str:
    """Renders the tiny query -> router -> rag/sql -> answer diagram,
    lighting up whichever path was actually taken for the last query."""
    DIM = "#1e3a5f"
    DIM_T = "#4a6080"
    EDGE = "#2a4a6a"

    RAG_C = "#1f6feb" if active_route in ("rag", "both") else DIM
    SQL_C = "#2563eb" if active_route in ("sql", "both") else DIM
    RAG_T = "#f3f6fb" if active_route in ("rag", "both") else DIM_T
    SQL_T = "#f3f6fb" if active_route in ("sql", "both") else DIM_T
    QBOX = "#10a37f" if active_route else DIM
    QT = "#f3f6fb" if active_route else DIM_T
    RBOX = "#10a37f" if active_route else DIM
    RT = "#f3f6fb" if active_route else DIM_T

    def arrow(active):
        return "#10a37f" if active else EDGE

    A_RAG = arrow(active_route in ("rag", "both"))
    A_SQL = arrow(active_route in ("sql", "both"))
    A_IN = arrow(bool(active_route))

    svg = f"""<svg viewBox="0 0 620 200" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;max-width:620px;font-family:monospace;display:block;">
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#10a37f"/>
    </marker>
    <marker id="arr-dim" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="{EDGE}"/>
    </marker>
  </defs>
  <rect x="10" y="80" width="110" height="40" rx="8" fill="{QBOX}" opacity="0.9"/>
  <text x="65" y="105" text-anchor="middle" fill="{QT}" font-size="12" font-weight="bold">User Query</text>
  <line x1="120" y1="100" x2="175" y2="100" stroke="{A_IN}" stroke-width="2" marker-end="url(#arr)"/>
  <rect x="175" y="75" width="110" height="50" rx="8" fill="{RBOX}" opacity="0.9"/>
  <text x="230" y="97" text-anchor="middle" fill="{RT}" font-size="12" font-weight="bold">Router</text>
  <text x="230" y="114" text-anchor="middle" fill="{RT}" font-size="10" opacity="0.75">guardrail · rewrite</text>
  <line x1="285" y1="88" x2="390" y2="50" stroke="{A_RAG}" stroke-width="2" marker-end="url(#arr)"/>
  <line x1="285" y1="112" x2="390" y2="150" stroke="{A_SQL}" stroke-width="2" marker-end="url(#arr)"/>
  <rect x="390" y="25" width="110" height="50" rx="8" fill="{RAG_C}" opacity="0.9"/>
  <text x="445" y="47" text-anchor="middle" fill="{RAG_T}" font-size="12" font-weight="bold">RAG</text>
  <text x="445" y="64" text-anchor="middle" fill="{RAG_T}" font-size="10" opacity="0.75">hybrid search</text>
  <rect x="390" y="125" width="110" height="50" rx="8" fill="{SQL_C}" opacity="0.9"/>
  <text x="445" y="147" text-anchor="middle" fill="{SQL_T}" font-size="12" font-weight="bold">SQL</text>
  <text x="445" y="164" text-anchor="middle" fill="{SQL_T}" font-size="10" opacity="0.75">self-correcting</text>
  <line x1="500" y1="50" x2="555" y2="90" stroke="{A_RAG}" stroke-width="2" marker-end="url(#arr)"/>
  <line x1="500" y1="150" x2="555" y2="110" stroke="{A_SQL}" stroke-width="2" marker-end="url(#arr)"/>
  <rect x="555" y="80" width="55" height="40" rx="8" fill="{QBOX}" opacity="0.9"/>
  <text x="582" y="105" text-anchor="middle" fill="{QT}" font-size="11" font-weight="bold">Answer</text>
</svg>"""
    return svg

