"""
Centralised LLM client.

All engines import `chat_complete` and `chat_complete_json` from here instead
of creating their own OpenAI() instances. The default target is a LOCAL Ollama
server (OpenAI-compatible API at localhost:11434/v1) running our fine-tuned
model, so the runtime makes zero cloud calls. Any OpenAI-compatible endpoint
still works by changing OPENAI_BASE_URL / OPENAI_MODEL.

Retry behaviour
---------------
Transient 429 / 503 errors (remote providers, or Ollama while a model loads)
are retried with exponential back-off.
"""

import time
import json
import re
from typing import Any, Iterator, Optional

from openai import OpenAI, RateLimitError, APIStatusError
from loguru import logger

from app.core.config import settings

# ── Single shared client (module-level singleton) ─────────────────────────
_client = OpenAI(
    api_key=settings.openai_api_key or "ollama",
    base_url=settings.openai_base_url or None,  # None → default OpenAI URL
    timeout=settings.llm_timeout_seconds,
)

# Ollama's OpenAI layer supports response_format=json_object (constrained JSON
# decoding), which makes small local models far more reliable at emitting JSON.
_IS_LOCAL = "localhost" in (settings.openai_base_url or "") or "127.0.0.1" in (settings.openai_base_url or "")


# ── Retry wrapper ─────────────────────────────────────────────────────────

def _call_with_retry(fn, *args, max_retries: int = 2, base_delay: float = 1.5, **kwargs):
    """
    Call `fn(*args, **kwargs)` with exponential back-off on 429 / 503.
    Raises the last exception if all retries are exhausted.
    """
    delay = base_delay
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except RateLimitError as e:
            if attempt == max_retries:
                raise
            logger.warning(
                f"Rate-limited (attempt {attempt + 1}/{max_retries}). "
                f"Retrying in {delay:.0f}s… ({e})"
            )
            time.sleep(delay)
            delay *= 2
        except APIStatusError as e:
            # 503 Service Unavailable — also transient
            if e.status_code == 503 and attempt < max_retries:
                logger.warning(f"503 from API, retrying in {delay:.0f}s…")
                time.sleep(delay)
                delay *= 2
            else:
                raise


# ── Public helpers ────────────────────────────────────────────────────────

def chat_complete(
    messages: list[dict],
    *,
    model: Optional[str] = None,
    temperature: float = 0,
    max_tokens: int = 1000,
    **kwargs,
) -> str:
    """
    Plain text completion. Returns the assistant message content as a string.
    """
    resp = _call_with_retry(
        _client.chat.completions.create,
        model=model or settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def chat_complete_json(
    messages: list[dict],
    *,
    model: Optional[str] = None,
    temperature: float = 0,
    max_tokens: int = 2000,
    **kwargs,
) -> Any:
    """
    JSON-object completion. Returns the parsed Python object.

    On a local Ollama server we pass response_format=json_object (constrained
    decoding). Remote providers (e.g. Gemini's compat layer) sometimes return
    None content with that flag, so for them we rely on the system nudge and
    parse the raw text ourselves, stripping any markdown fences.
    """
    # Inject a system nudge to guarantee JSON output without the API flag
    forced_messages = list(messages)
    has_system = any(m.get("role") == "system" for m in forced_messages)
    json_instruction = "Respond with a valid JSON object only. No markdown fences, no prose, no explanation. Output must start with { and end with }."
    if not has_system:
        forced_messages = [
            {"role": "system", "content": json_instruction},
        ] + forced_messages
    else:
        for i, m in enumerate(forced_messages):
            if m.get("role") == "system":
                forced_messages[i] = {**m, "content": m["content"] + f"\n\n{json_instruction}"}
                break

    if _IS_LOCAL:
        kwargs.setdefault("response_format", {"type": "json_object"})

    resp = _call_with_retry(
        _client.chat.completions.create,
        model=model or settings.openai_model,
        messages=forced_messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    raw = resp.choices[0].message.content or ""

    # Strip markdown fences: ```json ... ``` or ``` ... ```
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        stripped = "\n".join(inner).strip()

    if not stripped:
        logger.error("LLM returned empty content for JSON request")
        return {}

    # Strip any leading non-JSON characters (e.g. Gemini sometimes prepends ": ")
    brace_pos = stripped.find('{')
    if brace_pos > 0:
        stripped = stripped[brace_pos:]

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Last resort: pull first {...} block
        m = re.search(r'\{.*\}', stripped, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        logger.error(f"JSON parse failed. Raw: {raw[:300]}")
        return {}


def chat_stream(
    messages: list[dict],
    *,
    model: Optional[str] = None,
    temperature: float = 0,
    max_tokens: int = 1000,
) -> Iterator[str]:
    """
    Streaming completion. Yields text deltas as they are generated
    (used by the SSE chat endpoint).
    """
    stream = _call_with_retry(
        _client.chat.completions.create,
        model=model or settings.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for event in stream:
        if event.choices and event.choices[0].delta.content:
            yield event.choices[0].delta.content


def vision_complete(
    text_prompt: str,
    image_b64: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 500,
) -> str:
    """
    Vision completion — describe an image given a text prompt.
    Returns the assistant message as a string, or "" when no vision model is
    configured (the default for the local runtime).
    """
    if not (model or settings.openai_vision_model):
        return ""
    resp = _call_with_retry(
        _client.chat.completions.create,
        model=model or settings.openai_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text",      "text": text_prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{image_b64}"
                    }},
                ],
            }
        ],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""
