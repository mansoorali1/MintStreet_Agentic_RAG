"""
Thin wrapper around the Groq chat completions call.

Both the SQL engine and the graph nodes need to talk to Groq, so this lives
on its own instead of being duplicated or awkwardly owned by one of them.
"""

from app.clients import groq
from app.config import GROQ_GENERATION_MODEL


def call_groq(
    messages,
    model=GROQ_GENERATION_MODEL,
    temperature=0.1,
    max_tokens=1000,
    reasoning_effort=None,
    reasoning_format=None,
):
    """Send a chat completion request and return just the text.

    reasoning_effort / reasoning_format are only passed through when set,
    since not every model on Groq supports them - the routing/classification
    calls use "low" + "hidden" to keep the reasoning tokens out of the
    response, everything else leaves these alone.
    """
    kwargs = {}
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    if reasoning_format:
        kwargs["reasoning_format"] = reasoning_format

    response = groq.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return response.choices[0].message.content.strip()
