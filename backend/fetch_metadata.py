#!/usr/bin/env python3
"""Fetch and cache OSDR study metadata.

Usage:
    python -m backend.fetch_metadata                  # crawl ALL OSD studies (default)
    python -m backend.fetch_metadata --all --limit 10 # crawl first 10 (smoke test)
    python -m backend.fetch_metadata --curated        # only the curated eye/SANS list
    python -m backend.fetch_metadata OSD-87 OSD-100   # specific studies
    python -m backend.fetch_metadata --search         # keyword-discover extra studies
    python -m backend.fetch_metadata --force          # ignore cache, re-fetch
"""
import json
import time
import argparse
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from backend.config import (
    OSDR_FILES_URL, OSDR_SEARCH_URL, OSDR_STUDY_TYPE,
    METADATA_DIR, INDEX_FILE, DATA_DIR,
    EYE_SANS_STUDY_IDS, EYE_SANS_KEYWORDS,
)

PAGE_SIZE = 100
FILE_WORKERS = 6


def fetch_json(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OSDR-ChatBot/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"  Retry {attempt + 1}/{retries} after error: {e}")
            time.sleep(2)


def _join(value) -> str:
    """Coerce OSDR fields (which may be str, list, or nested) to a flat string."""
    if isinstance(value, list):
        return ", ".join(_join(v) for v in value if v)
    if isinstance(value, dict):
        return value.get("Name") or value.get("name") or json.dumps(value)
    return str(value or "")


def build_metadata(study_id: str, source: dict, file_count: int, files: list) -> dict:
    """Assemble the cached study record from a search `_source` + file listing."""
    return {
        "study_id": study_id,
        "title": _join(source.get("Study Title") or source.get("Project Title")),
        "description": _join(source.get("Study Description")),
        "organism": _join(source.get("organism")),
        "material_type": _join(source.get("Material Type")),
        "assay_measurement": _join(source.get("Study Assay Measurement Type")),
        "assay_platform": _join(source.get("Study Assay Technology Platform")),
        "assay_technology": _join(source.get("Study Assay Technology Type")),
        "study_factor": _join(source.get("Study Factor Name")),
        "mission": source.get("Mission", {}),
        "project_type": _join(source.get("Project Type")),
        "flight_program": _join(source.get("Flight Program")),
        "publication_title": _join(source.get("Study Publication Title")),
        "publication_authors": _join(source.get("Study Publication Author List")),
        "managing_center": _join(source.get("Managing NASA Center")),
        "release_date": _join(source.get("Study Public Release Date")),
        "file_count": file_count,
        "files": files,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def fetch_file_listing(study_id: str) -> tuple[int, list]:
    """Fetch (file_count, files) for one study. API needs the numeric ID."""
    numeric_id = study_id.replace("OSD-", "").strip()
    url = f"{OSDR_FILES_URL}/{numeric_id}/?page=1&size=500&all_files=true"
    try:
        data = fetch_json(url)
        study_data = data.get("studies", {}).get(study_id, {})
        return study_data.get("file_count", 0), study_data.get("study_files", [])
    except Exception as e:
        print(f"  [!] File listing failed for {study_id}: {e}")
        return 0, []


def fetch_all_sources(limit: int | None = None) -> dict[str, dict]:
    """Paginate the OSD study index, returning {accession: _source}."""
    sources: dict[str, dict] = {}
    start = 0
    while True:
        url = f"{OSDR_SEARCH_URL}?type={OSDR_STUDY_TYPE}&size={PAGE_SIZE}&from={start}"
        data = fetch_json(url)
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break
        for h in hits:
            src = h.get("_source", {})
            acc = src.get("Accession", "")
            if acc.startswith("OSD-"):
                sources[acc] = src
        print(f"  [.] enumerated {len(sources)} studies...")
        if limit and len(sources) >= limit:
            break
        start += PAGE_SIZE
    if limit:
        sources = dict(list(sources.items())[:limit])
    return sources


def fetch_details_by_accession(study_id: str) -> dict:
    """Fetch a single study's `_source` by accession (for explicit-ID mode)."""
    encoded = urllib.parse.quote(study_id)
    url = f"{OSDR_SEARCH_URL}?ffield=Accession&fvalue={encoded}&size=1&from=0"
    try:
        hits = fetch_json(url).get("hits", {}).get("hits", [])
        return hits[0].get("_source", {}) if hits else {}
    except Exception:
        return {}


def search_studies(keyword: str, size: int = 20) -> list[str]:
    encoded = urllib.parse.quote(keyword)
    url = f"{OSDR_SEARCH_URL}?ffield=Study+Title&fvalue={encoded}&size={size}&from=0"
    try:
        hits = fetch_json(url).get("hits", {}).get("hits", [])
        return [h["_source"]["Accession"] for h in hits
                if h.get("_source", {}).get("Accession", "").startswith("OSD-")]
    except Exception as e:
        print(f"  [!] Search failed for '{keyword}': {e}")
        return []


def save_study(study_id: str, metadata: dict) -> Path:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    path = METADATA_DIR / f"{study_id}.json"
    path.write_text(json.dumps(metadata, indent=2))
    return path


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {}


def save_index(index: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(index, indent=2))


def crawl(sources: dict[str, dict], index: dict) -> dict:
    """Fetch file listings (threaded) and persist metadata for each study."""
    todo = [sid for sid in sources if sid not in index]
    skipped = len(sources) - len(todo)
    if skipped:
        print(f"  [=] {skipped} already cached, skipping")
    print(f"  [>] fetching file listings for {len(todo)} studies ({FILE_WORKERS} workers)...")

    done = 0
    with ThreadPoolExecutor(max_workers=FILE_WORKERS) as pool:
        futures = {pool.submit(fetch_file_listing, sid): sid for sid in todo}
        for fut in as_completed(futures):
            sid = futures[fut]
            file_count, files = fut.result()
            meta = build_metadata(sid, sources[sid], file_count, files)
            save_study(sid, meta)
            index[sid] = {"file_count": file_count, "title": meta["title"],
                          "fetched_at": meta["fetched_at"]}
            done += 1
            if done % 25 == 0 or done == len(todo):
                print(f"  [+] {done}/{len(todo)} studies cached")
    return index


def main():
    parser = argparse.ArgumentParser(description="Fetch OSDR study metadata")
    parser.add_argument("study_ids", nargs="*", help="Specific OSD study IDs to fetch")
    parser.add_argument("--all", action="store_true", help="Crawl ALL OSD studies (default)")
    parser.add_argument("--curated", action="store_true", help="Only the curated eye/SANS list")
    parser.add_argument("--search", action="store_true", help="Keyword-discover extra studies")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if already cached")
    parser.add_argument("--limit", type=int, help="Cap number of studies (smoke test)")
    args = parser.parse_args()

    index = {} if args.force else load_index()

    # Resolve which studies to fetch and their _source metadata.
    if args.study_ids:
        ids = [s.upper() if s.upper().startswith("OSD-") else f"OSD-{s}" for s in args.study_ids]
        print(f"Fetching {len(ids)} specified studies...")
        sources = {sid: fetch_details_by_accession(sid) for sid in ids}
    elif args.curated:
        ids = list(EYE_SANS_STUDY_IDS)
        print(f"Fetching {len(ids)} curated eye/SANS studies...")
        sources = {sid: fetch_details_by_accession(sid) for sid in ids}
    else:
        print(f"Enumerating all OSD studies (type={OSDR_STUDY_TYPE})...")
        sources = fetch_all_sources(limit=args.limit)
        print(f"Found {len(sources)} studies.")

    if args.search:
        print("\nSearching OSDR for additional eye/SANS studies...")
        extra = set()
        for kw in EYE_SANS_KEYWORDS:
            for acc in search_studies(kw):
                if acc not in sources:
                    extra.add(acc)
        for acc in extra:
            sources[acc] = fetch_details_by_accession(acc)
        if extra:
            print(f"  Added {len(extra)} discovered studies: {', '.join(sorted(extra))}")

    print(f"\nCrawling metadata for {len(sources)} studies...")
    index = crawl(sources, index)
    save_index(index)
    print(f"\nDone. {len(index)} studies cached in {METADATA_DIR}")


if __name__ == "__main__":
    main()
