import os
import uuid
from datetime import datetime, timezone

def now_iso() -> str:
    """Returns the current time in ISO 8601 format with UTC timezone."""
    return datetime.now(timezone.utc).isoformat()

ASSISTANT_ID = uuid.UUID(os.getenv("ASSISTANT_ID", "11111111-1111-1111-1111-111111111111"))

ASSISTANT = {
    "assistant_id": str(ASSISTANT_ID),
    "graph_id": "echo",
    "name": "Echo Assistant",
    "description": "Replies with exactly what you said.",
    "config": {},
    "context": {},
    "created_at": now_iso(),
    "updated_at": now_iso(),
}
