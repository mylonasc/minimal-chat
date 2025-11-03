# main.py
import uuid
from time import sleep
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Path, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

# --- Refactored Imports ---
from services.storage import db
from services.streaming import get_stream_generator
from utils import extract_user_text, resolve_assistant_id, now_iso
from config import ASSISTANT_ID

# -----------------------
# App Setup
# -----------------------
app = FastAPI(title="LangGraph Echo API (Refactored)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# Assistants
# -----------------------
@app.post("/assistants/search")
def assistants_search(payload: Dict[str, Any] = Body(default={})):
    offset = int(payload.get("offset", 0) or 0)
    assistants = db.search_assistants()
    headers = {"x-offset": str(offset)}
    return JSONResponse(content=assistants, headers=headers)

@app.get("/assistants/{assistant_id}/schemas")
def assistants_schemas(assistant_id: str = Path(...)):
    schemas = db.get_schemas(assistant_id)
    if not schemas:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return schemas

# -----------------------
# Threads
# -----------------------
@app.post("/threads")
def create_thread(payload: Dict[str, Any] = Body(default={})):
    thread_data = db.create_thread(payload)
    return JSONResponse(content=thread_data, status_code=200)

@app.get("/threads/{thread_id}")
def get_thread(thread_id: str = Path(...)):
    t = db.get_thread(thread_id)
    if not t:
        raise HTTPException(status_code=4404, detail="Thread not found")
    return t

@app.post("/threads/search")
def search_threads(payload: Dict[str, Any] = Body(default={})):
    offset = int(payload.get("offset", 0) or 0)
    limit = int(payload.get("limit", 50) or 50)
    
    page = db.search_threads(offset, limit)
    total_items = db.get_total_threads()

    headers = {"x-offset": str(offset)}
    if offset + limit < total_items:
        headers["x-next-offset"] = str(offset + limit)
    
    return JSONResponse(content=page, headers=headers)

# -----------------------
# Runs (Non-streaming)
# -----------------------
@app.post("/threads/{thread_id}/runs")
def create_run(thread_id: str = Path(...), payload: Dict[str, Any] = Body(...)):
    if not db.get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    
    payload["assistant_id"] = resolve_assistant_id(payload)
    if str(payload.get("assistant_id")) != str(ASSISTANT_ID):
        raise HTTPException(status_code=400, detail="Unknown assistant_id")

    user_text = extract_user_text(payload).strip()

    # Delegate run creation to the storage service
    run = db.create_run(thread_id, payload, user_text) 
    
    headers = {"Content-Location": f"/threads/{thread_id}/runs/{run['run_id']}"}
    return JSONResponse(content=run, headers=headers)

# -----------------------
# Runs (Streaming)
# -----------------------
@app.post("/threads/{thread_id}/runs/stream")
async def stream_run(thread_id: str = Path(...), payload: dict = Body(default={})):
    
    # 1. Validate thread
    thread_checkpoints = db.get_thread_checkpoints(thread_id)
    if thread_checkpoints is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # 2. Basic Run Setup
    payload.setdefault("assistant_id", str(ASSISTANT_ID))
    text = extract_user_text(payload).strip()
    run_id = str(uuid.uuid4())
    
    run_data = {
        "run_id": run_id,
        "thread_id": thread_id,
        "assistant_id": str(ASSISTANT_ID),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "running", # Will be updated by the streamer
        "metadata": payload.get("metadata", {}),
        "kwargs": {},
        "multitask_strategy": "enqueue",
    }
    # Immediately add the run to the "DB" in a 'running' state
    db.add_run(run_data)

    # 3. Get the generator
    #    This is the key decoupling point.
    gen = await get_stream_generator(
        thread_id=thread_id,
        run_id=run_id,
        run_data=run_data,
        text=text,
        thread_checkpoints=thread_checkpoints
    )

    # 4. Stream the response
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen, media_type="text/event-stream", headers=headers)

# -----------------------
# History
# -----------------------
@app.post("/threads/{thread_id}/history")
def thread_history(thread_id: str, payload: dict = Body(default={})):
    sleep(0.5) # Reduced sleep, 2s is a long time
    
    offset = int(payload.get("offset", 0) or 0)
    limit = int(payload.get("limit", 50) or 50)

    page = db.get_history(thread_id, offset, limit)
    if page is None:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    total_items = db.get_history_count(thread_id)
    
    headers = {"x-offset": str(offset)}
    if offset + limit < total_items:
        headers["x-next-offset"] = str(offset + limit)

    return JSONResponse(content=page, headers=headers)

@app.post("/threads/{thread_id}/history/search")
def thread_history_search(thread_id: str, payload: dict = Body(default={})):
    # This just aliases the history endpoint
    return thread_history(thread_id, payload)

# -----------------------
# Health
# -----------------------
@app.get("/ok")
def ok():
    return {"ok": True}

@app.get("/info")
def info():
    return {"name": "echo-api-refactored", "version": "1.0.0"}
