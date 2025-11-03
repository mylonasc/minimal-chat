# utils.py
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from config import ASSISTANT_ID

def now_iso() -> str:
    """Returns the current time in ISO 8601 format with UTC timezone."""
    return datetime.now(timezone.utc).isoformat()

def sse(event: str, data: dict | list, id_: int | None = None) -> str:
    """Formats an SSE frame with multi-line data."""
    parts = []
    if id_ is not None:
        parts.append(f"id: {id_}")
    parts.append(f"event: {event}")

    json_data_str = json.dumps(data, ensure_ascii=False, indent=2)
    for line in json_data_str.splitlines():
        parts.append(f"data: {line}")

    return "\n".join(parts) + "\n\n"

def resolve_assistant_id(payload: dict) -> str:
    """
    Accepts:
     - exact assistant_id
     - or graph_id == "echo"
     - or nothing (defaults to the only assistant)
    """
    incoming = str(payload.get("assistant_id") or "").strip()
    if incoming == str(ASSISTANT_ID):
        return str(ASSISTANT_ID)
    if payload.get("graph_id") == "echo":
        return str(ASSISTANT_ID)
    return str(ASSISTANT_ID)


def extract_user_text(payload: dict) -> str:
    """
    Accepts many payload shapes and extracts the user's text.
    Returns "" if nothing usable is found.
    """
    def _from_content(content) -> str | None:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            # Check for messages list inside
            msgs_inner = content.get("messages")
            if isinstance(msgs_inner, list):
                for m in reversed(msgs_inner):
                    if isinstance(m, dict) and m.get("type") in ("user", "human"):
                        cand = m.get("content")
                        if isinstance(cand, str):
                            return cand

            # Check for common text keys
            for k in ("text", "content", "input", "prompt", "query", "message"):
                v = content.get(k)
                if isinstance(v, str):
                    return v

        if isinstance(content, list):
            # OpenAI-style content parts: [{"type":"text","text":"..."}]
            for part in content:
                if isinstance(part, dict):
                    if isinstance(part.get("text"), str):
                        return part["text"]
                    for k in ("content", "input", "prompt"):
                        v = part.get(k)
                        if isinstance(v, str):
                            return v
        return None

    # 1) direct input (V2 style)
    inp = payload.get("input")
    if isinstance(inp, str):
        return inp
    if isinstance(inp, dict) or isinstance(inp, list):
        cand = _from_content(inp)
        if isinstance(cand, str):
            return cand

    # 2) messages array (V1 style)
    msgs = payload.get("messages")
    if isinstance(msgs, list):
        for m in reversed(msgs):
            if isinstance(m, dict) and m.get("role") in ("user", "human"):
                cand = _from_content(m.get("content"))
                if isinstance(cand, str):
                    return cand

    return ""
