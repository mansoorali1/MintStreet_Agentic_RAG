"""
Turns a SQL result set into a matplotlib chart, picking the chart type
based on the shape of the data rather than a hardcoded type per query.
Styled to match the app's dark neon theme so it drops straight into the
chat without looking like a bolted-on default matplotlib plot.
"""

import io

import matplotlib
matplotlib.use("Agg")  # headless - no display backend inside the container
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

from app.clients import monthly_inv, yearly_inv


def pick_chart_type(df, x_col, y_cols, query=""):
    """Rule-based chart type selection based on data shape.
    Returns one of: 'line', 'bar', 'grouped_bar', 'horizontal_bar', 'donut'
    """
    n_rows = len(df)
    n_y_cols = len(y_cols)
    is_time = x_col in ("year", "month_year")

    share_keywords = ["share", "ratio", "percent", "composition", "proportion", "breakdown"]
    if n_y_cols == 1 and any(k in y_cols[0].lower() for k in share_keywords):
        return "donut"
    if n_y_cols == 1 and df[y_cols[0]].sum() > 80 and df[y_cols[0]].sum() < 120:
        return "donut"

    if is_time and n_rows >= 3:
        if n_y_cols >= 3:
            return "grouped_bar"
        return "line"

    if not is_time:
        if n_y_cols == 1:
            avg_label_len = df[x_col].astype(str).str.len().mean()
            return "horizontal_bar" if avg_label_len > 10 else "bar"
        return "grouped_bar"

    if n_rows == 2:
        return "bar"

    return "line"


def generate_chart(sql_json: str, title: str = "") -> Image.Image | None:
    """Generates a chart from the SQL result JSON produced by sql_node.
    Returns a PIL image, or None when a chart wouldn't add anything
    (e.g. a single-row result, or no numeric columns to plot)."""
    if not sql_json:
        return None

    try:
        df = pd.read_json(io.StringIO(sql_json), convert_dates=["month_year"])
    except Exception:
        return None

    if df.empty or len(df) < 2:
        return None

    x_col = None
    for candidate in ["year", "month_year"]:
        if candidate in df.columns:
            x_col = candidate
            break
    if x_col is None:
        for col in df.columns:
            if df[col].dtype == object:
                x_col = col
                break
    if x_col is None:
        return None

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    y_cols = [c for c in numeric_cols if c != x_col]
    if not y_cols:
        return None
    y_cols = y_cols[:3]  # keep it readable, don't cram 6 lines onto one chart

    BG_OUTER = "#071426"
    BG_INNER = "#0c1f36"
    GRID_CLR = "#28405f"
    TEXT_CLR = "#f3f6fb"
    LABEL_CLR = "#b8c4d9"
    COLORS = ["#10a37f", "#2563eb", "#f59e0b", "#8b5cf6", "#ef4444"]

    def convert_values(col, values):
        if "_vol" in col or "volume" in col.lower():
            return values / 10000, "Billions"
        elif "_val" in col or "value" in col.lower():
            return values / 100000, "₹ Trillion"
        return values, ""

    def get_label(col):
        readable = yearly_inv.get(col, monthly_inv.get(col, col))
        parts = readable.split("_")
        return " ".join(parts[-3:]) if len(parts) > 3 else readable

    def get_x_labels(df, x_col):
        if pd.api.types.is_datetime64_any_dtype(df[x_col]):
            return pd.to_datetime(df[x_col]).dt.strftime("%b-%Y")
        return df[x_col].astype(str)

    chart_type = pick_chart_type(df, x_col, y_cols)

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(BG_OUTER)
    ax.set_facecolor(BG_INNER)

    unit = ""
    if chart_type == "line":
        for i, col in enumerate(y_cols):
            vals, unit = convert_values(col, df[col].values.astype(float))
            label = f"{get_label(col)} ({unit})" if unit else get_label(col)
            ax.plot(get_x_labels(df, x_col), vals, marker="o", linewidth=2.5,
                    markersize=6, color=COLORS[i % len(COLORS)], label=label)
            if i == 0:
                ax.fill_between(get_x_labels(df, x_col), vals, alpha=0.08, color=COLORS[0])

    elif chart_type == "bar":
        col = y_cols[0]
        vals, unit = convert_values(col, df[col].values.astype(float))
        bars = ax.bar(get_x_labels(df, x_col), vals, color=COLORS[0], alpha=0.85,
                      width=0.5, label=f"{get_label(col)} ({unit})" if unit else get_label(col))
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.01,
                    f"{bar.get_height():.1f}", ha="center", va="bottom",
                    color=TEXT_CLR, fontsize=8)

    elif chart_type == "grouped_bar":
        x = np.arange(len(df))
        width = 0.8 / len(y_cols)
        for i, col in enumerate(y_cols):
            vals, unit = convert_values(col, df[col].values.astype(float))
            offset = (i - len(y_cols) / 2 + 0.5) * width
            ax.bar(x + offset, vals, width, color=COLORS[i % len(COLORS)], alpha=0.85,
                   label=f"{get_label(col)} ({unit})" if unit else get_label(col))
        ax.set_xticks(x)
        ax.set_xticklabels(get_x_labels(df, x_col), rotation=45, ha="right")

    elif chart_type == "horizontal_bar":
        col = y_cols[0]
        vals, unit = convert_values(col, df[col].values.astype(float))
        y_pos = np.arange(len(df))
        ax.barh(y_pos, vals, color=COLORS[0], alpha=0.85,
                label=f"{get_label(col)} ({unit})" if unit else get_label(col))
        ax.set_yticks(y_pos)
        ax.set_yticklabels(get_x_labels(df, x_col), color=TEXT_CLR, fontsize=8)

    elif chart_type == "donut":
        col = y_cols[0]
        vals = df[col].values.astype(float)
        labels = get_x_labels(df, x_col).tolist()
        wedge_colors = COLORS[:len(vals)]
        wedges, texts, autotexts = ax.pie(
            vals, labels=labels, colors=wedge_colors, autopct="%1.1f%%",
            startangle=90, wedgeprops=dict(width=0.5, edgecolor=BG_OUTER, linewidth=2),
            textprops=dict(color=TEXT_CLR, fontsize=8))
        for at in autotexts:
            at.set_color(BG_OUTER)
            at.set_fontsize(8)
        ax.set_aspect("equal")

    if chart_type != "donut":
        ax.set_xlabel(x_col.replace("_", " ").title(), color=LABEL_CLR, fontsize=9)
        if unit:
            ax.set_ylabel(unit, color=LABEL_CLR, fontsize=9)
        ax.tick_params(colors=LABEL_CLR, labelsize=8)
        for spine in ["bottom", "left"]:
            ax.spines[spine].set_color(GRID_CLR)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if chart_type not in ("horizontal_bar",):
            ax.xaxis.set_tick_params(rotation=45)
        ax.grid(axis="y", color=GRID_CLR, linestyle="--", alpha=0.4)
        ax.legend(facecolor=BG_INNER, labelcolor=TEXT_CLR, fontsize=8, framealpha=0.8)

    if title:
        ax.set_title(title[:70], color=TEXT_CLR, fontsize=10, pad=12, fontweight="bold")

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    img = Image.open(buf).copy()
    plt.close(fig)
    return img
