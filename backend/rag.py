"""Real RAG retrieval over the ChromaDB study index.

Replaces the old keyword-count `build_context`: embeds the query with
nomic-embed-text and pulls the most semantically similar study chunks.
"""
import chromadb

from backend.config import (
    CHROMA_DIR, CHROMA_COLLECTION, OLLAMA_EMBED_MODEL, RAG_TOP_K,
)
from backend import ollama_client

SYSTEM_PROMPT = """You are an expert scientific assistant specializing in NASA's Open Science Data Repository (OSDR) and space biology / space medicine.

You are given metadata retrieved from OSDR studies relevant to the user's question.

When answering:
- Cite specific OSD study IDs (e.g. OSD-87, OSD-679) when relevant
- Distinguish between human studies and animal/microbial models
- Note whether data comes from actual spaceflight vs. ground-based analogs (head-down tilt, hindlimb unloading)
- Be precise about assay types (RNA-seq, proteomics, histology, IOP measurements, etc.)
- If the retrieved context does not answer the question, say so — do not fabricate study details

The retrieved OSDR context is provided below."""

_collection = None


def get_collection():
    """Lazily open the persistent Chroma collection (cached per process)."""
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"}
        )
    return _collection


def retrieve(query: str, k: int = RAG_TOP_K) -> list[dict]:
    """Return the top-k most similar chunks as dicts with study_id/text/distance."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    q_emb = ollama_client.embed(query, OLLAMA_EMBED_MODEL)
    res = collection.query(query_embeddings=[q_emb], n_results=k)
    hits = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        hits.append({
            "study_id": meta.get("study_id", ""),
            "title": meta.get("title", ""),
            "text": doc,
            "distance": dist,
        })
    return hits


def build_context(query: str, k: int = RAG_TOP_K) -> tuple[str, list[str]]:
    """Retrieve, group by study, and format a cited context block.

    Returns (context_string, [ordered unique source study IDs]).
    """
    hits = retrieve(query, k)
    if not hits:
        return "", []

    order: list[str] = []
    grouped: dict[str, list[str]] = {}
    titles: dict[str, str] = {}
    for h in hits:
        sid = h["study_id"]
        if sid not in grouped:
            grouped[sid] = []
            order.append(sid)
            titles[sid] = h["title"]
        grouped[sid].append(h["text"])

    lines = [f"Retrieved metadata from {len(order)} OSDR studies:\n"]
    for sid in order:
        lines.append(f"\n[{sid}] {titles.get(sid, '')}")
        for chunk in grouped[sid]:
            lines.append(f"  {chunk}")
    return "\n".join(lines), order
