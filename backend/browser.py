"""FastAPI backend for the OSDR Study Browser.

A second, read-only entry point into the same metadata cache + vector store as
the chatbot: browse all cached OSD studies, semantic-search them, and inspect a
single study's record. Runs as its own service (port 8078) with its own OOD
portal tile, distinct from the chat app on 8077.

Endpoints:
    GET /api/studies      list cached studies (id, title, file_count)
    GET /api/study/{id}   full cached record for one study
    GET /api/search       semantic study search
    GET /                 the browse UI

Run: uvicorn backend.browser:app --port 8078
"""
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from backend.config import METADATA_DIR, INDEX_FILE, RAG_TOP_K
from backend import rag

app = FastAPI(title="OSDR Study Browser")

_STATIC = METADATA_DIR.parent.parent / "backend" / "browser_static"


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


@app.get("/")
def index():
    return FileResponse(_STATIC / "index.html")
