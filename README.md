# OSDR ChatBot

A local **RAG chatbot** for exploring NASA's [Open Science Data Repository (OSDR)](https://osdr.nasa.gov/) built 
from all OSDR study metadata (588 studies as of July 10, 2026).

This system runs entirely locally: study metadata is crawled from the OSDR API, embedded with a local
embedding model, and stored in a vector database. At query time, a local LLM (via [ollama](https://ollama.com/))
answers questions grounded in the studies retrieved by semantic search. Ships with a **React web UI**
(streaming answers, cited studies, browser-saved history). It also runs locally from the terminal.

It is fully hosted and running live here: [https://datahive.uwyo.edu/osdr/](https://datahive.uwyo.edu/osdr/). The
server is configured with 72-core Intel(R) Xeon(R) Gold 6150 CPU and a single Tesla V100-DGXS-32GB GPU, 503GB
System RAM. Contact Dr. Jian Gong at the University of Wyoming for hosting or server-related questions.

**Study Browser** for exploring the cached corpus.
---

## Architecture

```
  ┌──────────── ingest (one-time / on refresh) ────────────┐   ┌──────── query time ────────┐

                 fetch_metadata.py                 ingest.py
 OSDR API  ───────────────────────►  data/metadata/*.json  ───────────────────►  ChromaDB
 (588 studies)   crawl + file lists      (one JSON / study)   chunk + embed        (vector index)
                                                              (nomic-embed-text)          │
                                                                                          │
                                                                       rag.py: embed query,
                                                                       retrieve top-k chunks
                                                                                          │
 Browser (React)  ┐                                                                       ▼
   localStorage    ├─◄──SSE──  FastAPI (backend/app.py)  ◄──── grounded context ── + gemma4 (ollama)
   cited chips     │             /api/chat /api/studies                              generate answer
 CLI (chatbot.py) ─┘             /api/study /api/search /api/models
```

- **Real RAG** — nomic-embed-text embeddings + ChromaDB cosine search (not keyword matching).
- **Local & offline at query time** — embeddings and the chat model both run through ollama.
- **Two front ends, one backend** — the React web UI and the CLI both call the same `rag.py`
  retrieval + `ollama_client.py` generation path.
- **Browser history** — conversations persist in `localStorage`; survive reloads.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | Backend, crawl, ingest |
| Node.js 18+ | Frontend (React + Vite) |
| [ollama](https://ollama.com/) running | `ollama serve` |
| A chat model | default `gemma4` — any installed model works via `--model` / the UI picker |
| `nomic-embed-text` | `ollama pull nomic-embed-text` (embeddings) |

---

## Quick Start

```bash
# 1. Backend deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Models (skip any you already have)
ollama pull nomic-embed-text
ollama pull gemma4                     # or use any model you have

# 3. Crawl OSDR metadata (all 588 studies; ~a few minutes)
python -m backend.fetch_metadata           # or: --all --limit 20 for a quick test

# 4. Build the vector index
python -m backend.ingest --rebuild

# 5a. Run the web app
uvicorn backend.app:app --port 8077        # backend API
cd frontend && npm install && npm run dev  # dev UI at http://localhost:5173

# 5b. …or use the CLI
python chatbot.py
```

> **Production build:** `cd frontend && npm run build` then just run `uvicorn backend.app:app --port 8077`
> — FastAPI serves the built UI at `http://localhost:8077/`.

> **Port note:** the backend defaults to **8077** (port 8000 is commonly taken). The Vite dev proxy in
> `frontend/vite.config.js` points at 8077 — change both together if you use a different port.

---

## Fetching Metadata

```bash
python -m backend.fetch_metadata              # crawl ALL OSD studies (default)
python -m backend.fetch_metadata --all --limit 25   # first 25 (smoke test)
python -m backend.fetch_metadata --curated    # only the curated eye/SANS list
python -m backend.fetch_metadata OSD-87 OSD-583     # specific studies
python -m backend.fetch_metadata --search     # keyword-discover extra eye/SANS studies
python -m backend.fetch_metadata --force      # ignore cache, re-fetch
```

Each study is saved to `data/metadata/OSD-NNN.json` (title, description, organism, assay, mission,
publication, and the full file listing) plus a lightweight `data/index.json`. Re-run `ingest` after
fetching to refresh the vector index.

### OSDR API endpoints

| Purpose | Endpoint |
|---------|----------|
| Enumerate studies | `GET /osdr/data/search?type=cgene&size=100&from=N` (paginated, ~588 total) |
| File listing | `GET /osdr/data/osd/files/{numeric_id}/?page=1&size=500&all_files=true` |
| Study by accession | `GET /osdr/data/search?ffield=Accession&fvalue=OSD-87&size=1` |

> The files endpoint needs the **numeric** ID (`87`), not the accession (`OSD-87`).

---

## Web API (FastAPI)

`backend/app.py` (default port 8077):

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat` | Stream an answer (SSE: `sources` → `token`s → `done`). Body: `{message, history, model?}` |
| GET | `/api/studies` | List cached studies (id, title, file_count) |
| GET | `/api/study/{id}` | Full cached record for one study |
| GET | `/api/search?q=` | Semantic study search |
| GET | `/api/models` | Installed ollama models (for the picker) |
| GET | `/` | The built React UI (after `npm run build`) |

---

## Configuration

All settings live in `backend/config.py`:

```python
OLLAMA_MODEL        = "gemma4"            # default chat model (UI/CLI can override)
OLLAMA_EMBED_MODEL  = "nomic-embed-text"  # embedding model
CHROMA_DIR          = DATA_DIR / "chroma" # persistent vector store
RAG_TOP_K           = 10                   # chunks retrieved per query
EYE_SANS_STUDY_IDS  = [...]               # curated list for --curated
EYE_SANS_KEYWORDS   = [...]               # for --search discovery
```

---

## Project Structure

```
OSDR_Chatbot/
├── backend/
│   ├── config.py           # model, paths, endpoints, curated lists
│   ├── ollama_client.py     # embed(), chat_stream(), model discovery
│   ├── fetch_metadata.py    # crawl OSDR → data/metadata/*.json
│   ├── ingest.py            # chunk + embed → ChromaDB
│   ├── rag.py               # semantic retrieval + cited context
│   └── app.py               # FastAPI (SSE chat, studies, search, models)
├── chatbot.py              # CLI front end (reuses the backend)
├── frontend/                # React + Vite SPA (chatbot)
│   └── src/{App.jsx, api.js, components/, hooks/useConversations.js}
├── requirements.txt
└── data/  (gitignored)      # metadata/, index.json, chroma/
```

---

## Background — What Is SANS?

**Space Associated Neuro-ocular Syndrome (SANS)** is a condition seen in some astronauts after
long-duration spaceflight (optic disc edema, globe flattening, choroidal folds, hyperopic shifts,
elevated intracranial pressure) — likely tied to cephalad fluid shifts in microgravity. The curated
`--curated` list and eye/SANS keywords remain available, but the default corpus now spans **all** of
OSDR, so you can ask about any space-biology topic in the repository.

**Further reading:** [NASA HRP — SANS](https://www.nasa.gov/hrp/elements/sans) ·
[OSDR Repository Search](https://osdr.nasa.gov/bio/repo/search)

---

## License

Not affiliated with NASA. Data is fetched from the publicly accessible OSDR API.
