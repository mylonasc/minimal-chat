# data_utils.py
import uuid
from typing import List, Dict, Any, Optional

from utils import now_iso
from config import ASSISTANT_ID

def make_checkpoint(
    checkpoint_id: str,
    parent_checkpoint_id: str | None,
    thread_id: str,
    run_id: str,
    step: int,
    messages: list
) -> dict:
    """Creates a mock checkpoint object."""
    return {
        "values": {
            "messages": messages
        },
        "next": [],
        "tasks": [],
        "metadata": {
            "graph_id": "agent",
            "assistant_id": str(ASSISTANT_ID),
            "run_id": run_id,
            "thread_id": thread_id,
            "step": step,
        },
        "created_at": now_iso(),
        "checkpoint": {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
        },
        "parent_checkpoint": {
            "thread_id": thread_id,
            "checkpoint_id": parent_checkpoint_id,
        } if parent_checkpoint_id else None
    }


def make_msg(role: str, content: str) -> dict:
    """Helper to create timestamped messages."""
    return {
        "id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "role": role,
        "content": content,
        "type": "human" if role == "user" else "ai",
        "additional_kwargs": {},
        "response_metadata": {},
        "tool_calls": [],
        "invalid_tool_calls": [],
    }

def make_metadata_chunk(run_id: str, thread_id: str, step: int) -> dict:
    """Creates a mock metadata chunk object."""
    return {
        "tags": [f"graph:step:{step}"],
        "created_by": "system",
        "graph_id": "agent",
        "assistant_id": str(ASSISTANT_ID),
        "run_attempt": 1,
        "langgraph_version": "0.2.35", # Mock
        "langgraph_plan": "developer", # Mock
        "langgraph_host": "self-hosted", # Mock
        "run_id": run_id,
        "thread_id": thread_id,
        "langgraph_step": step,
        "langgraph_node": "callModel", # Mock
    }
