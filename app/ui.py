"""
Gradio UI - CSS theme, layout, and all the event wiring. Building this
inside app.ui() means importing app.ui gives you a ready `demo` object
that main.py just launches; nothing in here runs a dev server on import.

RBI_QUESTIONS backs the "suggested questions" pills - update this list
whenever the underlying data or reports change.
"""

import uuid

import gradio as gr

from app.chat_handler import chat
from app.formatters import build_flowchart_svg

RBI_QUESTIONS = {
    "Data": [
        "What was the total UPI transaction volume and value in 2023-24?",
        "Show the year-on-year growth of total digital payments from 2016 to 2024.",
        "Compare UPI, NEFT, and IMPS transaction volumes for the last 5 years.",
        "What is the CAGR of UPI transactions from 2018-19 to 2023-24?",
        "Show monthly UPI volume and value trends for the financial year 2023-24."
    ],
    "Policy": [
        "What concerns did the RBI raise about digital payment fraud in recent annual reports?",
        "How has RBI addressed cybersecurity risks in India's digital payment ecosystem?",
        "What regulatory initiatives did RBI introduce to promote financial inclusion through digital payments?",
        "What did RBI say about the interoperability of payment systems in India?",
        "How has RBI's stance on prepaid payment instruments (PPIs) evolved over the years?"
    ],
    "Hybrid": [
        "Compare UPI transaction growth data with RBI's policy commentary on UPI adoption.",
        "What did RBI say about IMPS and what does the transaction volume data show?",
        "Show NEFT transaction trends and explain RBI's strategic rationale for NEFT promotion.",
        "How did RBI respond to mobile payment growth and what does the monthly data show?",
        "Combine credit card transaction data with RBI's observations on card-based payments."
    ]
}
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg-main:          #071426;
    --bg-card:          #0c1f36;
    --bg-card-2:        #102744;
    --border:            rgba(100,150,220,0.18);
    --border-active:    rgba(59,130,246,0.45);
    --text-primary:     #f3f6fb;
    --text-secondary:   #b8c4d9;
    --text-muted:       #6a84a8;
    --accent:           #3b82f6;
    --accent-green:     #10a37f;
    --success:          #22c55e;
    --neon-cyan:        rgba(0, 210, 220, 0.75);
    --neon-glow-outer:  rgba(0, 210, 220, 0.18);
    --neon-glow-inner:  rgba(0, 210, 220, 0.08);
}

*, *::before, *::after { box-sizing: border-box; }

body, .gradio-container, .gradio-container * {
    font-family: 'Sora', sans-serif !important;
    color: var(--text-primary) !important;
}

body, .gradio-container {
    background:
        radial-gradient(ellipse at 0% 0%, rgba(30,64,175,0.22) 0%, transparent 50%),
        radial-gradient(ellipse at 100% 0%, rgba(16,163,127,0.12) 0%, transparent 45%),
        #071426 !important;
    min-height: 100vh;
}

footer { display: none !important; }

/* ── Header ── */
.rbi-header {
    padding: 18px 24px;
    margin-bottom: 0px;
    background: rgba(12,31,54,0.85);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 16px 16px 0 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.rbi-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary) !important;
    letter-spacing: -0.3px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* Hide native Gradio tab bar entirely */
.tabs > .tab-nav {
    display: none !important;
}

/* Custom tab nav row */
.custom-tab-nav-row {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    width: 100% !important;
    background: rgba(12,31,54,0.85) !important;
    border-left: 1px solid var(--border) !important;
    border-right: 1px solid var(--border) !important;
    border-bottom: 1px solid var(--border) !important;
    border-radius: 0 0 0 0 !important;
    padding: 0 16px !important;
    gap: 0 !important;
    margin-bottom: 0 !important;
}

/* Individual tab nav buttons */
.custom-tab-btn {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    color: var(--text-muted) !important;
    padding: 10px 18px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    border-radius: 0 !important;
    margin-bottom: -1px !important;
    transition: all 0.15s ease !important;
    height: auto !important;
    box-shadow: none !important;
    font-family: 'Sora', sans-serif !important;
}
.custom-tab-btn:hover {
    color: #ffffff !important;
    background: rgba(59,130,246,0.08) !important;
}
.custom-tab-btn-active {
    color: #00d2dc !important;
    border-bottom: 2px solid #00d2dc !important;
}

/* Flex spacer to push NEW CHAT to the right */
.custom-tab-spacer {
    flex-grow: 1 !important;
    background: transparent !important;
    border: none !important;
    pointer-events: none !important;
}

/* ── NEW CHAT inline button ── */
#rbi-newchat-inline-btn {
    background-color: rgba(16, 163, 127, 0.1) !important;
    border: 1px solid #10a37f !important;
    color: #10a37f !important;
    border-radius: 6px !important;
    padding: 6px 18px !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    cursor: pointer !important;
    height: auto !important;
    min-width: unset !important;
    max-width: unset !important;
    width: auto !important;
    white-space: nowrap !important;
    margin-left: 10px !important;
    margin-right: 8px !important;
    box-shadow: none !important;
    transition: all 0.2s ease !important;
    font-family: 'Sora', sans-serif !important;
    letter-spacing: 0.5px !important;
    flex-shrink: 0 !important;
}
#rbi-newchat-inline-btn:hover {
    background-color: #10a37f !important;
    color: #ffffff !important;
    box-shadow: 0 0 10px rgba(16, 163, 127, 0.4) !important;
}

/* Chatbot container */
.chatbot-wrap > .label-wrap,
.chatbot-wrap label { display: none !important; }
.chatbot-wrap .delete-btn,
.chatbot-wrap button[aria-label="Clear"],
.chatbot-wrap button[title="Clear"],
.chatbot-wrap .icon-button { display: none !important; }
.chatbot-wrap .copy-text-button { opacity: 0.3 !important; }

#chatbot {
    height: 520px !important;
    overflow-y: auto !important;
    border: 2px solid var(--neon-cyan) !important;
    border-radius: 16px !important;
    background: rgba(7, 20, 38, 0.6) !important;
    backdrop-filter: blur(12px) !important;
    box-shadow:
        0 0 15px 3px var(--neon-glow-outer),
        inset 0 0 10px 0px var(--neon-glow-inner) !important;
}

#chatbot > div,
#chatbot > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* User & Bot speech bubbles */
#chatbot .message.user,
.chatbot-wrap .message.user {
    background: #1e4a8a !important;
    border: 1px solid rgba(100,160,255,0.2) !important;
    border-radius: 18px 18px 4px 18px !important;
    color: white !important;
    font-size: 14px !important;
    max-width: 75% !important;
    margin-left: auto !important;
    padding: 14px 18px !important;
}

#chatbot .message.bot,
.chatbot-wrap .message.bot {
    background: #0f2744 !important;
    border: 1px solid rgba(59,130,246,0.15) !important;
    border-radius: 18px 18px 18px 4px !important;
    color: white !important;
    font-size: 14px !important;
    max-width: 85% !important;
    padding: 14px 18px !important;
}

#chatbot .message, .chatbot-wrap .message {
    background: transparent !important; border: none !important; padding: 0 !important; box-shadow: none !important;
}

#chatbot .message *, #chatbot .bubble-wrap *, #chatbot p, #chatbot span,
#chatbot li, #chatbot strong, #chatbot em, #chatbot code,
.chatbot-wrap .message *, .chatbot-wrap p, .chatbot-wrap span {
    color: var(--text-primary) !important;
}

/* Input text bar styling */
.input-row {
    display: flex; align-items: center; gap: 12px; padding: 14px 0 8px 0; border-top: 1px solid var(--border);
}

.msg-textbox, .msg-textbox > div, .msg-textbox > div > div {
    background: transparent !important; border: none !important; box-shadow: none !important;
}

.msg-textbox textarea {
    background: #071426 !important; color: white !important;
    border: 1px solid rgba(59,130,246,0.4) !important; border-radius: 12px !important;
    padding: 14px 16px !important; font-size: 14px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    scrollbar-width: none !important; /* Firefox */
    -ms-overflow-style: none !important;  /* IE/Edge */
    resize: none !important;
    overflow-y: hidden !important;
}
.msg-textbox textarea::placeholder { color: var(--text-muted) !important; opacity: 0.8 !important; }
.msg-textbox textarea:focus {
    border-color: var(--neon-cyan) !important;
    box-shadow: 0 0 12px 2px var(--neon-glow-outer) !important; outline: none !important;
}
# .msg-textbox textarea::-webkit-scrollbar {
#     display: none !important;
# }

.send-btn {
    width: 48px !important; min-width: 48px !important; height: 44px !important;
    border-radius: 10px !important; background: #2563eb !important; border: none !important;
    color: white !important; font-size: 20px !important; cursor: pointer !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
    transition: background 0.15s, transform 0.1s !important;
}
.send-btn:hover { background: #3b82f6 !important; transform: scale(1.03); }

/* Native Pill UI Overrides matching your aesthetic */
.pills-layout-container {
    display: flex; align-items: center; gap: 16px; margin-top: 14px;
}
.suggested-label-wrap {
    font-size: 14px; font-weight: 700; color: #ffffff !important; white-space: nowrap;
}
.bolt-icon { color: #f59e0b !important; margin-right: 6px; font-size: 16px; }

.rbi-pill-group-btn {
    background: rgba(16, 39, 68, 0.6) !important;
    border: 1px solid rgba(90,130,200,0.3) !important;
    color: #b8c4d9 !important;
    border-radius: 12px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 6px 0 !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    min-width: 110px !important;
    width: 110px !important;
    text-align: center !important;
    box-shadow: none !important;
}
.rbi-pill-group-btn:hover {
    color: #ffffff !important;
    background: rgba(59,130,246,0.08) !important;
    border-color: rgba(0, 210, 220, 0.4) !important;
}
.rbi-pill-group-btn-active {
    background: rgba(59,130,246,0.18) !important;
    border: 1px solid var(--neon-cyan) !important;
    color: #ffffff !important;
    box-shadow: 0 0 10px rgba(0,210,220,0.25) !important;
}

/* Suggested Question List Items Styling */
# .suggested-q-list-btn {
#     background: transparent !important;
#     border: none !important;
#     color: #b8c4d9 !important;
#     font-size: 13px !important;
#     text-align: left !important;
#     cursor: pointer !important;
#     padding: 4px 0 !important;
#     transition: color 0.15s !important;
#     box-shadow: none !important;
#     width: 100% !important;
# }
# .suggested-q-list-btn:hover {
#     color: #00d2dc !important;
# }

# #rbi-question-area-column {
#     margin-left: 185px !important;
#     max-width: 600px !important;
# }
#rbi-question-area-column {
    margin-left: 0 !important;
    max-width: 100% !important;
    padding: 8px 0 4px 0 !important;
}

.suggested-q-list-btn {
    background: rgba(12,31,54,0.8) !important;
    border: 1px solid rgba(100,150,220,0.18) !important;
    border-radius: 12px !important;
    color: #b8c4d9 !important;
    font-size: 13px !important;
    text-align: left !important;
    cursor: pointer !important;
    padding: 12px 14px !important;
    transition: border-color 0.2s, box-shadow 0.2s, background 0.2s, color 0.2s !important;
    box-shadow: none !important;
    width: 100% !important;
    line-height: 1.45 !important;
}
.suggested-q-list-btn:hover {
    border-color: rgba(0, 210, 220, 0.75) !important;
    background: rgba(16,39,68,0.9) !important;
    color: #f3f6fb !important;
    box-shadow: 0 0 12px 2px rgba(0,210,220,0.18) !important;
}

/* Trace styles */
# .trace-label {
#     font-size: 12px !important; font-weight: 700 !important; color: #f3f6fb !important;
#     text-transform: uppercase !important; letter-spacing: 1.4px !important; margin-bottom: 6px !important; display: block;
# }
# .trace-box {
#     background: #071426 !important; border: 1px solid var(--neon-cyan) !important; border-radius: 14px !important;
#     padding: 16px !important; margin-bottom: 18px !important;
#     box-shadow: 0 0 10px 2px var(--neon-glow-outer), inset 0 0 8px 0px var(--neon-glow-inner) !important;
# }
# .trace-box > *, .trace-box div { background: #071426 !important; border: none !important; box-shadow: none !important; }
# .trace-box pre code { color: #7dd3fc !important; font-family: 'JetBrains Mono', monospace !important; }
/* Trace styles */
# .trace-label {
#     font-size: 12px !important; font-weight: 700 !important; color: #f3f6fb !important;
#     text-transform: uppercase !important; letter-spacing: 1.4px !important; margin-bottom: 6px !important; display: block;
# }
# .trace-box {
#     background: #071426 !important; border: 1px solid var(--neon-cyan) !important; border-radius: 14px !important;
#     padding: 16px !important; margin-bottom: 18px !important;
#     box-shadow: 0 0 10px 2px var(--neon-glow-outer), inset 0 0 8px 0px var(--neon-glow-inner) !important;
# }
# /* FIXED: Excluded syntax wrappers from global overrides to restore query code colors */
# .trace-box > *, .trace-box div:not(.code-wrapper):not(pre):not(code) {
#     background: #071426 !important;
#     border: none !important;
#     box-shadow: none !important;
# }
# .trace-box pre code {
#     color: #7dd3fc !important;
#     font-family: 'JetBrains Mono', monospace !important;
# }

/* Trace styles */
.trace-label {
    font-size: 12px !important; font-weight: 700 !important; color: #f3f6fb !important;
    text-transform: uppercase !important; letter-spacing: 1.4px !important; margin-bottom: 6px !important; display: block;
}
.trace-box {
    background: #071426 !important; border: 1px solid var(--neon-cyan) !important; border-radius: 14px !important;
    padding: 16px !important; margin-bottom: 18px !important;
    box-shadow: 0 0 10px 2px var(--neon-glow-outer), inset 0 0 8px 0px var(--neon-glow-inner) !important;
}

/* Force dark backgrounds on ALL inner layout elements, tables, and wrappers within Trace */
.trace-box,
.trace-box div,
.trace-box p,
.trace-box .prose,
.trace-box .markdown-text {
    background: #071426 !important;
    border: none !important;
    box-shadow: none !important;
}

/* TARGET THE ACTUAL CODE BLOCK: Restores dark container + enables syntax visibility */
.trace-box pre, .trace-box .code-wrapper {
    background: #0b1d33 !important; /* Slightly distinct dark shade for the block code */
    border: 1px solid rgba(100,150,220,0.18) !important;
    border-radius: 10px !important;
    padding: 12px 14px !important;
}

.trace-box pre code {
    font-family: 'JetBrains Mono', monospace !important;
    background: transparent !important;
}

.badge {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px;
    background: #10a37f; color: white; font-size: 10px; font-weight: 700; margin-left: 6px;
}
.flowchart-label {
    font-size: 12px !important; font-weight: 700 !important; color: #f3f6fb !important;
    text-transform: uppercase !important; letter-spacing: 1.4px !important; margin: 16px 0 8px 2px !important; display: block;
}
.flowchart-box {
    background: #071426 !important; border: 1px solid var(--neon-cyan) !important; border-radius: 14px !important;
    padding: 20px 16px !important; box-shadow: 0 0 10px 2px var(--neon-glow-outer), inset 0 0 8px 0px var(--neon-glow-inner) !important;
}
.flowchart-box > *, .flowchart-box div { background: #071426 !important; border: none !important; box-shadow: none !important; }

.citations-strip {
    margin: -6px 0 10px 4px;
    font-family: 'Sora', sans-serif !important;
}
.citations-strip details summary { outline: none; }
"""

# ── Gradio UI Setup ────────────────────────────────────────────────────────────
# Applied the base theme properly to Blocks constructor directly to avoid any warnings
with gr.Blocks(theme="base", css=CSS) as demo:

    session_id        = gr.State(value=lambda: str(uuid.uuid4()))
    trace_badge_count = gr.State(value=0)
    active_pill       = gr.State(value="")

    # ── Header ─────────────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="rbi-header">
        <div class="rbi-title">
            🏛️ MintStreet — Agentic RAG for RBI Digital Payments
        </div>
    </div>
    """)

    # ── Custom Tab Navigation Row ──
    with gr.Row(elem_classes=["custom-tab-nav-row"]):
        btn_chat_tab  = gr.Button("💬 Chat",  elem_classes=["custom-tab-btn", "custom-tab-btn-active"])
        btn_trace_tab = gr.Button("🔍 Trace", elem_classes=["custom-tab-btn"])
        gr.HTML("<div class='custom-tab-spacer'></div>")
        btn_new_chat  = gr.Button("＋ NEW CHAT", elem_id="rbi-newchat-inline-btn")

    # ── Panel A: Chat View Workspace ──────────────────────────────────────────
    with gr.Column(visible=True) as chat_panel:

        chatbot = gr.Chatbot(
            label="",
            show_label=False,
            elem_id="chatbot",
            elem_classes="chatbot-wrap",
            show_copy_button=False,
            type="messages",
            avatar_images=(
                None,
                "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Reserve_Bank_of_India_seal.svg/240px-Reserve_Bank_of_India_seal.svg.png"
            ),
        )

        # citations_display = gr.HTML(value="", visible=False, elem_classes="citations-strip")

        with gr.Row(elem_classes="input-row"):
            msg_input = gr.Textbox(
                placeholder="Ask about UPI growth, RBI policy, payment trends...",
                show_label=False,
                scale=10,
                container=False,
                elem_classes="msg-textbox",
                lines=1,
                max_lines=4,
            )
            send_btn = gr.Button("↑", variant="primary", scale=0, elem_classes="send-btn", min_width=48)

        # ── NATIVE GRADIO PILL COMPONENT IMPLEMENTATION ──
        with gr.Row(elem_classes=["pills-layout-container"]):
            gr.HTML('<div class="suggested-label-wrap"><span class="bolt-icon">⚡</span>Suggested Questions</div>')
            pill_data   = gr.Button("📊 Data",   elem_classes=["rbi-pill-group-btn"])
            pill_policy = gr.Button("📋 Policy", elem_classes=["rbi-pill-group-btn"])
            pill_hybrid = gr.Button("🔀 Hybrid", elem_classes=["rbi-pill-group-btn"])

        # Collapsible Context-Driven Question List Row
        # Collapsible Context-Driven Question List Row
        with gr.Row(visible=False, elem_id="rbi-question-sub-row") as questions_row:
            with gr.Column(elem_id="rbi-question-area-column"):
                with gr.Row():
                    q_btn_1 = gr.Button("", elem_classes=["suggested-q-list-btn"])
                    q_btn_2 = gr.Button("", elem_classes=["suggested-q-list-btn"])
                with gr.Row():
                    q_btn_3 = gr.Button("", elem_classes=["suggested-q-list-btn"])
                    q_btn_4 = gr.Button("", elem_classes=["suggested-q-list-btn"])
                with gr.Row():
                    q_btn_5 = gr.Button("", elem_classes=["suggested-q-list-btn"])

    # ── Panel B: Trace View Workspace ──────────────────────────────────────────
    with gr.Column(visible=False) as trace_panel:
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=200):
                gr.HTML('<span class="trace-label">Execution Summary</span>')
                with gr.Group(elem_classes="trace-box"):
                    exec_summary_display = gr.Markdown(value="*Run a query to see execution details.*")

            with gr.Column(scale=2):
                gr.HTML('<span class="trace-label">Generated Query</span>')
                with gr.Group(elem_classes="trace-box"):
                    generated_query_display = gr.Markdown(value="*SQL queries will appear here for data questions.*")

        gr.HTML('<span class="flowchart-label">Query Routing</span>')
        with gr.Group(elem_classes="flowchart-box"):
            flowchart_display = gr.HTML(value=build_flowchart_svg(""))

    badge_display = gr.HTML(value="", visible=False)

    # ── Native Python Backend Logic for Pill Options Management ────────────────
    def toggle_pill_selection(category, current_active):
        if current_active == category:
            return (
                gr.update(elem_classes=["rbi-pill-group-btn"]),
                gr.update(elem_classes=["rbi-pill-group-btn"]),
                gr.update(elem_classes=["rbi-pill-group-btn"]),
                gr.update(visible=False),
                "",
            ) + tuple(gr.update(value="") for _ in range(5))

        qs = RBI_QUESTIONS.get(category, [""] * 5)

        c_data = ["rbi-pill-group-btn", "rbi-pill-group-btn-active"] if category == "Data" else ["rbi-pill-group-btn"]
        c_policy = ["rbi-pill-group-btn", "rbi-pill-group-btn-active"] if category == "Policy" else ["rbi-pill-group-btn"]
        c_hybrid = ["rbi-pill-group-btn", "rbi-pill-group-btn-active"] if category == "Hybrid" else ["rbi-pill-group-btn"]

        return (
            gr.update(elem_classes=c_data),
            gr.update(elem_classes=c_policy),
            gr.update(elem_classes=c_hybrid),
            gr.update(visible=True),
            category,
            gr.update(value=qs[0]),
            gr.update(value=qs[1]),
            gr.update(value=qs[2]),
            gr.update(value=qs[3]),
            gr.update(value=qs[4]),
        )

    def choose_question(question_text):
        clean_text = question_text.lstrip("• ").strip()
        return (
            clean_text,
            gr.update(visible=False),
            gr.update(elem_classes=["rbi-pill-group-btn"]),
            gr.update(elem_classes=["rbi-pill-group-btn"]),
            gr.update(elem_classes=["rbi-pill-group-btn"]),
            ""
        )

    # ── Tab Navigation Switching Handlers ──────────────────────────────────────
    def switch_to_chat():
        return (
            gr.update(visible=True), gr.update(visible=False),
            gr.update(elem_classes=["custom-tab-btn", "custom-tab-btn-active"]),
            gr.update(elem_classes=["custom-tab-btn"]),
        )

    def switch_to_trace():
        return (
            gr.update(visible=False), gr.update(visible=True),
            gr.update(elem_classes=["custom-tab-btn"]),
            gr.update(elem_classes=["custom-tab-btn", "custom-tab-btn-active"]),
        )

    btn_chat_tab.click(fn=switch_to_chat, outputs=[chat_panel, trace_panel, btn_chat_tab, btn_trace_tab])
    btn_trace_tab.click(fn=switch_to_trace, outputs=[chat_panel, trace_panel, btn_chat_tab, btn_trace_tab])
    def handle_new_chat():
        return (
            [], "",
            "*Run a query to see execution details.*",
            "*SQL queries will appear here for data questions.*",
            build_flowchart_svg(""), 0,
            gr.update(visible=True), gr.update(visible=False),
            gr.update(elem_classes=["custom-tab-btn", "custom-tab-btn-active"]),
            gr.update(elem_classes=["custom-tab-btn"]),
            gr.update(visible=False),
            gr.update(elem_classes=["rbi-pill-group-btn"]),
            gr.update(elem_classes=["rbi-pill-group-btn"]),
            gr.update(elem_classes=["rbi-pill-group-btn"]),
            "",
            gr.update(value="", visible=False),   # citations_display reset
        )
    # ── Core Interface Wiring Execution Pipes ─────────────────────────────────
    def on_send(message, history, session_id, badge_count):
        return chat(message, history, session_id, badge_count)

    def update_badge_html(count):
        count = int(count)
        if count == 0: return ""
        return f"""
        <script>
        (function() {{
            var tabs = document.querySelectorAll('.custom-tab-btn');
            for (var i = 0; i < tabs.length; i++) {{
                var t = tabs[i];
                if (t.textContent.indexOf('Trace') !== -1) {{
                    var old = t.querySelector('.badge');
                    if (old) old.remove();
                    var badge = document.createElement('span');
                    badge.className   = 'badge';
                    badge.textContent = '{count}';
                    t.appendChild(badge);
                }}
            }}
        }})();
        </script>"""
    # Wire Main Pill Clicks to toggle questions list view natively
    pill_data.click(fn=toggle_pill_selection, inputs=[gr.State("Data"), active_pill], outputs=[pill_data, pill_policy, pill_hybrid, questions_row, active_pill, q_btn_1, q_btn_2, q_btn_3, q_btn_4, q_btn_5])
    pill_policy.click(fn=toggle_pill_selection, inputs=[gr.State("Policy"), active_pill], outputs=[pill_data, pill_policy, pill_hybrid, questions_row, active_pill, q_btn_1, q_btn_2, q_btn_3, q_btn_4, q_btn_5])
    pill_hybrid.click(fn=toggle_pill_selection, inputs=[gr.State("Hybrid"), active_pill], outputs=[pill_data, pill_policy, pill_hybrid, questions_row, active_pill, q_btn_1, q_btn_2, q_btn_3, q_btn_4, q_btn_5])

    # Wire List Item Sub-Buttons to Copy Value directly to Input Textbox
    for target_q_btn in [q_btn_1, q_btn_2, q_btn_3, q_btn_4, q_btn_5]:
        target_q_btn.click(fn=choose_question, inputs=[target_q_btn], outputs=[msg_input, questions_row, pill_data, pill_policy, pill_hybrid, active_pill])

    btn_new_chat.click(
        fn=handle_new_chat,
        outputs=[
            chatbot, msg_input, exec_summary_display, generated_query_display, flowchart_display,
            trace_badge_count, chat_panel, trace_panel, btn_chat_tab, btn_trace_tab,
            questions_row, pill_data, pill_policy, pill_hybrid, active_pill
        ],
    )
    send_btn.click(
        fn=on_send, inputs=[msg_input, chatbot, session_id, trace_badge_count],
        outputs=[chatbot, exec_summary_display, generated_query_display, flowchart_display, trace_badge_count],
    ).then(fn=update_badge_html, inputs=[trace_badge_count], outputs=[badge_display]
    ).then(fn=lambda: "", outputs=[msg_input])

    msg_input.submit(
        fn=on_send, inputs=[msg_input, chatbot, session_id, trace_badge_count],
        outputs=[chatbot, exec_summary_display, generated_query_display, flowchart_display, trace_badge_count],
    ).then(fn=update_badge_html, inputs=[trace_badge_count], outputs=[badge_display]
    ).then(fn=lambda: "", outputs=[msg_input])

