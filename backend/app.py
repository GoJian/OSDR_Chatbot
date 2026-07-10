"""FastAPI backend for the OSDR RAG chatbot.

Endpoints:
    POST /api/chat        stream an answer (SSE): first a `sources` event, then `token`s, then `done`
    GET  /api/studies     list cached studies (id, title, file_count)
    GET  /api/study/{id}  full cached record for one study
    GET  /api/search      semantic study search (browse panel)
    GET  /api/models      installed ollama models (for the model picker)

Run: uvicorn backend.app:app --port 8000
"""
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.config import (
    OLLAMA_MODEL, OLLAMA_FALLBACK_MODEL, METADATA_DIR, INDEX_FILE, PROJECT_ROOT, RAG_TOP_K,
)
from backend import rag, ollama_client

app = FastAPI(title="OSDR ChatBot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    model: str | None = None


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/chat")
def chat(req: ChatRequest):
    # Resolve the requested (or default) model, falling back if unavailable.
    ok, resolved = ollama_client.resolve_model(req.model or OLLAMA_MODEL)
    if not ok:
        ok, resolved = ollama_client.resolve_model(OLLAMA_FALLBACK_MODEL)
    if not ok:
        raise HTTPException(status_code=503, detail=f"No usable ollama model: {resolved}")

    context, sources = rag.build_context(req.message, RAG_TOP_K)

    messages = [{"role": "system", "content": rag.SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"OSDR context:\n{context}"})
    messages.extend({"role": m.role, "content": m.content} for m in req.history)
    messages.append({"role": "user", "content": req.message})

    def stream():
        yield _sse("sources", {"studies": sources, "model": resolved})
        try:
            for token in ollama_client.chat_stream(resolved, messages):
                yield _sse("token", token)
        except Exception as e:
            yield _sse("error", str(e))
        yield _sse("done", True)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/studies")
def studies():
    if not INDEX_FILE.exists():
        return {"studies": [], "count": 0}
    index = json.loads(INDEX_FILE.read_text())
    items = [
        {"study_id": sid, "title": v.get("title", ""), "file_count": v.get("file_count", 0)}
        for sid, v in sorted(index.items())
    ]
    return {"studies": items, "count": len(items)}


@app.get("/api/study/{study_id}")
def study(study_id: str):
    path = METADATA_DIR / f"{study_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{study_id} not cached")
    return json.loads(path.read_text())


@app.get("/api/search")
def search(q: str, k: int = RAG_TOP_K):
    hits = rag.retrieve(q, k)
    # Collapse to unique studies, best (smallest) distance first.
    seen: dict[str, dict] = {}
    for h in hits:
        sid = h["study_id"]
        if sid not in seen:
            seen[sid] = {"study_id": sid, "title": h["title"], "score": round(1 - h["distance"], 3)}
    return {"results": list(seen.values())}


@app.get("/api/models")
def models():
    try:
        return {"models": ollama_client.list_models(), "default": OLLAMA_MODEL}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# --- Serve the built frontend (frontend/dist) at / when it exists ---
_DIST = PROJECT_ROOT / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(_DIST / "index.html")
