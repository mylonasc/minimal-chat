# services/streaming.py
import asyncio
import copy
import uuid
from typing import AsyncGenerator, List, Dict, Any

# Note: We import 'db' from storage to modify state
from services.storage import db
from data_utils import make_msg, make_checkpoint
from utils import sse, now_iso

class EchoStreamer:
    """
    Handles the logic for generating the echo stream.
    This is the component to swap with a real LangGraph/LangChain streamer.
    """

    def __init__(
        self,
        thread_id: str,
        run_id: str,
        run_data: Dict[str, Any],
        text: str,
        thread_checkpoints: List[Dict[str, Any]],
    ):
        self.thread_id = thread_id
        self.run_id = run_id
        self.run_data = run_data # This is the 'run' object, which we will mutate
        self.text = text
        self.latest_checkpoint = thread_checkpoints[0]
        self.event_id = 1

    async def stream_response(self) -> AsyncGenerator[str, None]:
        """The main async generator for the echo response."""
        try:
            # --- Initial Setup Events ---
            yield ":\n\n"  # Keepalive
            yield self._sse_metadata()
            yield self._sse_run_start()

            # --- Create and Send Checkpoints ---
            step_0_ckpt = self._create_step_0_checkpoint()
            db.add_checkpoint(self.thread_id, step_0_ckpt)
            yield self._sse_checkpoint(step_0_ckpt)
            
            step_1_ckpt = self._create_step_1_checkpoint(step_0_ckpt)
            db.add_checkpoint(self.thread_id, step_1_ckpt)
            yield self._sse_checkpoint(step_1_ckpt)

            # --- Stream "Tokens" (The Core Echo Logic) ---
            # This is the 'business logic' block you'd replace
            msg_content_path = f"/messages/{len(step_1_ckpt['values']['messages']) - 1}/content"
            full_content_chunks = []
            
            words = self.text.split()
            if not words and self.text == "":
                words = ["I didn't catch that!"]
            elif not words and self.text != "":
                words = [self.text]

            for word in words:
                chunk = word + " " if word != words[-1] else word
                full_content_chunks.append(chunk)

                yield self._sse_token(msg_content_path, chunk)

                # Update the in-memory checkpoint (at the front)
                # In a real app, this might be handled by LangGraph's checkpointer
                final_text = "".join(full_content_chunks)
                db.get_latest_checkpoint(self.thread_id)["values"]["messages"][-1]["content"] = final_text
                
                await asyncio.sleep(0.02) # Simulate work/network delay

            # --- Finalize Run and Checkpoint ---
            final_checkpoint = db.get_latest_checkpoint(self.thread_id)
            self._finalize_data(final_checkpoint, len(words))

            yield self._sse_run_end()
            yield self._sse_checkpoint_end(final_checkpoint)
            yield self._sse_stream_end(final_checkpoint)

        except BrokenPipeError:
            print(f"[{self.run_id}] Stream broken by client.")
            return
        except Exception as e:
            print(f"[{self.run_id}] Stream error: {e}")
            yield sse("error", {"run_id": self.run_id, "message": str(e)}, id_=self.event_id)
            self.event_id += 1
            yield sse("stream_end", {"run_id": self.run_id}, id_=self.event_id)

    
    # --- Helper methods to create data ---
    
    def _create_step_0_checkpoint(self) -> Dict[str, Any]:
        """Create the user input checkpoint."""
        user_msg = make_msg("user", self.text)
        messages = copy.deepcopy(self.latest_checkpoint["values"]["messages"])
        messages.append(user_msg)
        
        return make_checkpoint(
            checkpoint_id=f"{self.run_id}:step_0",
            parent_checkpoint_id=self.latest_checkpoint["checkpoint"]["checkpoint_id"],
            thread_id=self.thread_id,
            run_id=self.run_id,
            step=0,
            messages=messages
        )

    def _create_step_1_checkpoint(self, step_0_ckpt: Dict[str, Any]) -> Dict[str, Any]:
        """Create the initial (empty) assistant response checkpoint."""
        assistant_msg = make_msg("assistant", "") # Start with empty content
        messages = copy.deepcopy(step_0_ckpt["values"]["messages"])
        messages.append(assistant_msg)

        return make_checkpoint(
            checkpoint_id=f"{self.run_id}:step_1",
            parent_checkpoint_id=step_0_ckpt["checkpoint"]["checkpoint_id"],
            thread_id=self.thread_id,
            run_id=self.run_id,
            step=1,
            messages=messages
        )
    
    def _finalize_data(self, final_checkpoint: Dict[str, Any], num_words: int):
        """Mutates the run and checkpoint with final data."""
        # Finalize run status
        self.run_data["status"] = "success"
        self.run_data["updated_at"] = now_iso()
        
        # Finalize checkpoint with mock usage metadata
        final_checkpoint["updated_at"] = now_iso()
        final_checkpoint["values"]["messages"][-1]["response_metadata"] = {
            "usage": { 
                "prompt_tokens": 5, # Mock
                "completion_tokens": num_words, 
                "total_tokens": 5 + num_words 
            }
        }

    # --- Helper methods for SSE formatting ---
    # These helpers make the main generator more readable

    def _next_id(self) -> int:
        """Increments and returns the SSE event ID."""
        id_ = self.event_id
        self.event_id += 1
        return id_

    def _sse_metadata(self) -> str:
        return sse("metadata", {"run_id": self.run_id, "thread_id": self.thread_id}, id_=self._next_id())

    def _sse_run_start(self) -> str:
        return sse("data", [{"op": "add", "path": "/runs/-", "value": self.run_data}], id_=self._next_id())

    def _sse_checkpoint(self, checkpoint: Dict[str, Any]) -> str:
        return sse("data", [{"op": "add", "path": "/checkpoints/-", "value": checkpoint}], id_=self._next_id())

    def _sse_token(self, path: str, chunk: str) -> str:
        return sse(
            "data",
            [{"op": "add", "path": f"{path}/-", "value": chunk}],
            id_=self._next_id()
        )

    def _sse_run_end(self) -> str:
        return sse(
            "data",
            [{"op": "replace", "path": "/runs/0", "value": self.run_data}],
            id_=self._next_id()
        )
    
    def _sse_checkpoint_end(self, checkpoint: Dict[str, Any]) -> str:
        return sse(
            "data",
            [{"op": "replace", "path": "/checkpoints/0", "value": checkpoint}],
            id_=self._next_id()
        )

    def _sse_stream_end(self, checkpoint: Dict[str, Any]) -> str:
        return sse(
            "stream_end",
            {"run_id": self.run_id, "final_checkpoint": checkpoint},
            id_=self._next_id()
        )

# -----------------------------------------------------------------
# 💡 SWAPPABLE FACTORY 💡
# -----------------------------------------------------------------

async def get_stream_generator(
    thread_id: str,
    run_id: str,
    run_data: Dict[str, Any],
    text: str,
    thread_checkpoints: List[Dict[str, Any]],
) -> AsyncGenerator[str, None]:
    """
    Factory function to get the appropriate stream generator.
    
    This is where you would add your logic to swap implementations.
    For example, you could inspect `run_data["assistant_id"]` or
    `payload["graph_id"]` to decide which streamer to return.
    
    **To use LangGraph, you would:**
    1. Create a `LangGraphStreamer` class similar to `EchoStreamer`.
    2. Its `stream_response` method would call your `app.astream_events(...)`.
    3. You would yield formatted SSE events from that stream.
    4. Update this function to return `LangGraphStreamer(...).stream_response()`.
    """
    
    # For now, it's hard-coded to the EchoStreamer
    streamer = EchoStreamer(thread_id, run_id, run_data, text, thread_checkpoints)
    
    # Return the generator object itself
    return streamer.stream_response()
