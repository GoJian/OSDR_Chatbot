#!/usr/bin/env python3
"""Chunk cached OSDR study metadata, embed it, and load a ChromaDB collection.

Usage:
    python -m backend.ingest              # embed studies not yet indexed
    python -m backend.ingest --rebuild    # drop the collection and re-embed everything
"""
import json
import argparse

import chromadb

from backend.config import (
    METADATA_DIR, CHROMA_DIR, CHROMA_COLLECTION, OLLAMA_EMBED_MODEL,
)
from backend import ollama_client

DESC_CHUNK_CHARS = 800


def load_all_metadata() -> dict[str, dict]:
    """Load every cached study record from data/metadata/."""
    studies = {}
    if not METADATA_DIR.exists():
        return studies
    for path in sorted(METADATA_DIR.glob("OSD-*.json")):
        try:
            data = json.loads(path.read_text())
            studies[data["study_id"]] = data
        except Exception:
            pass
    return studies


def _mission_str(data: dict) -> str:
    m = data.get("mission", {})
    if isinstance(m, dict):
        return m.get("Name", "")
    if isinstance(m, list):
        return ", ".join(x.get("Name", "") if isinstance(x, dict) else str(x) for x in m)
    return str(m or "")


def study_chunks(data: dict) -> list[str]:
    """Turn one study record into embeddable text chunks (each self-describing)."""
    sid = data["study_id"]
    title = data.get("title", "")
    chunks = []

    # 1) Study card — the searchable summary.
    card = (
        f"{sid}: {title}\n"
        f"Organism: {data.get('organism','')} | Tissue/Material: {data.get('material_type','')}\n"
        f"Assay: {data.get('assay_measurement','')} / {data.get('assay_platform','')}\n"
        f"Factor: {data.get('study_factor','')} | Mission: {_mission_str(data)} | "
        f"Flight program: {data.get('flight_program','')}\n"
        f"Publication: {data.get('publication_title','')}"
    )
    chunks.append(card)

    # 2) Description — split long text so each chunk embeds cleanly.
    desc = (data.get("description") or "").strip()
    for i in range(0, len(desc), DESC_CHUNK_CHARS):
        piece = desc[i:i + DESC_CHUNK_CHARS]
        chunks.append(f"{sid} ({title}) description: {piece}")

    # 3) File summary — categories present in the study.
    files = data.get("files", [])
    if files:
        cats = sorted({f.get("category", "") for f in files if f.get("category")})
        if cats:
            chunks.append(
                f"{sid} ({title}) contains {data.get('file_count', len(files))} files "
                f"across categories: {', '.join(cats)}"
            )
    return chunks


def get_collection(rebuild: bool):
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if rebuild:
        try:
            client.delete_collection(CHROMA_COLLECTION)
        except Exception:
            pass
    return client.get_or_create_collection(
        CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"}
    )


def main():
    parser = argparse.ArgumentParser(description="Ingest OSDR metadata into ChromaDB")
    parser.add_argument("--rebuild", action="store_true", help="Drop and rebuild the collection")
    args = parser.parse_args()

    studies = load_all_metadata()
    if not studies:
        print("No cached metadata. Run: python -m backend.fetch_metadata")
        return

    collection = get_collection(args.rebuild)
    existing = set(collection.get(include=[])["ids"]) if not args.rebuild else set()

    ids, docs, embeddings, metadatas = [], [], [], []
    total = len(studies)
    for n, (sid, data) in enumerate(studies.items(), 1):
        chunks = study_chunks(data)
        for i, chunk in enumerate(chunks):
            cid = f"{sid}:{i}"
            if cid in existing:
                continue
            ids.append(cid)
            docs.append(chunk)
            embeddings.append(ollama_client.embed(chunk, OLLAMA_EMBED_MODEL))
            metadatas.append({
                "study_id": sid,
                "title": data.get("title", ""),
                "chunk_type": "card" if i == 0 else "detail",
            })
        if n % 25 == 0 or n == total:
            print(f"  [.] embedded {n}/{total} studies ({len(ids)} new chunks)")

    if not ids:
        print("Nothing new to embed. Collection is up to date.")
        return

    # Chroma has a per-call batch ceiling; add in batches to stay well under it.
    BATCH = 512
    for i in range(0, len(ids), BATCH):
        collection.add(
            ids=ids[i:i + BATCH],
            documents=docs[i:i + BATCH],
            embeddings=embeddings[i:i + BATCH],
            metadatas=metadatas[i:i + BATCH],
        )

    print(f"\nDone. Added {len(ids)} chunks. Collection now holds {collection.count()} chunks.")


if __name__ == "__main__":
    main()
