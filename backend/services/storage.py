# services/storage.py
import uuid
from typing import Any, Dict, List, Optional
from config import ASSISTANT, ASSISTANT_ID
from utils import now_iso
from data_utils import make_checkpoint

class InMemoryStorage:
    """
    Manages the in-memory state for assistants, threads, runs, and checkpoints.
    This entire class can be replaced with a persistent storage implementation
    (e.g., using SQL, Redis, etc.) without changing the FastAPI endpoints.
    """
    def __init__(self):
        self.assistants: Dict[str, Dict[str, Any]] = {str(ASSISTANT_ID): ASSISTANT}
        self.threads: Dict[str, Dict[str, Any]] = {}
        self.threads_checkpoint_list: Dict[str, List[Dict[str, Any]]] = {}
        self.runs: Dict[str, Dict[str, Any]] = {}

    def search_assistants(self) -> List[Dict[str, Any]]:
        return list(self.assistants.values())

    def get_schemas(self, assistant_id: str) -> Optional[Dict[str, Any]]:
        if assistant_id != str(ASSISTANT_ID):
            return None
        
        # Schemas copied from original app.py
        input_schema = {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["role", "content"],
                    },
                },
            },
            "additionalProperties": True,
        }
        output_schema = {
            "type": "object",
            "properties": {
                "output": {"type": "string"},
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["role", "content"],
                    },
                },
            },
            "additionalProperties": True,
        }
        return {"input_schema": input_schema, "output_schema": output_schema}

    def create_thread(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        thread_id = str(uuid.uuid4())
        now = now_iso()
        thread_data = {
            "thread_id": thread_id,
            "created_at": now,
            "updated_at": now,
            "metadata": payload.get("metadata", {}),
            "config": payload.get("config", {}),
            "context": payload.get("context", {}),
            "status": "idle",
            "values": {"messages": []},
            "interrupts": {},
            "tasks": [],
        }
        self.threads[thread_id] = thread_data

        start_ckpt = make_checkpoint(
            checkpoint_id=f"{uuid.uuid4()}",
            parent_checkpoint_id=None,
            thread_id=thread_id,
            run_id="<initial>",
            step=-1,
            messages=[]
        )
        self.threads_checkpoint_list[thread_id] = [start_ckpt]
        return thread_data

    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        return self.threads.get(thread_id)

    def search_threads(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        items = sorted(self.threads.values(), key=lambda t: t["updated_at"], reverse=True)
        return items[offset : offset + limit]

    def get_total_threads(self) -> int:
        return len(self.threads)

    def create_run(self, thread_id: str, payload: Dict[str, Any], user_text: str) -> Dict[str, Any]:
        """Creates a non-streaming run."""
        t = self.get_thread(thread_id)
        if not t:
            raise ValueError("Thread not found") # Should be caught by API layer

        assistant_msg = {"role": "assistant", "content": user_text}

        t["values"].setdefault("messages", [])
        if user_text and (not t["values"]["messages"] or t["values"]["messages"][-1].get("content") != user_text):
            t["values"]["messages"].append({"role": "user", "content": user_text})
        t["values"]["messages"].append(assistant_msg)
        t["updated_at"] = now_iso()
        t["status"] = "idle"

        run_id = str(uuid.uuid4())
        run = {
            "run_id": run_id,
            "thread_id": thread_id,
            "assistant_id": str(ASSISTANT_ID),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "status": "success",
            "metadata": payload.get("metadata", {}),
            "kwargs": {"result": {"output": user_text, "messages": [assistant_msg]}},
            "multitask_strategy": "enqueue",
        }
        self.runs[run_id] = run
        return run

    def add_run(self, run_data: Dict[str, Any]):
        """Adds a run, typically in a 'running' state for streaming."""
        run_id = run_data["run_id"]
        self.runs[run_id] = run_data

    def get_thread_checkpoints(self, thread_id: str) -> Optional[List[Dict[str, Any]]]:
        return self.threads_checkpoint_list.get(thread_id)
    
    def get_latest_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        checkpoints = self.get_thread_checkpoints(thread_id)
        return checkpoints[0] if checkpoints else None

    def add_checkpoint(self, thread_id: str, checkpoint: Dict[str, Any]):
        """Adds a new checkpoint to the front of the list (newest first)."""
        self.threads_checkpoint_list[thread_id].insert(0, checkpoint)

    def get_history(self, thread_id: str, offset: int, limit: int) -> Optional[List[Dict[str, Any]]]:
        checkpoints = self.get_thread_checkpoints(thread_id)
        if checkpoints is None:
            return None
        return checkpoints[offset : offset + limit]

    def get_history_count(self, thread_id: str) -> int:
        checkpoints = self.get_thread_checkpoints(thread_id)
        return len(checkpoints) if checkpoints else 0

# Create a single "db" instance to be used by the app
db = InMemoryStorage()
