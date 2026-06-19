#!/usr/bin/env python3
"""
Fetch and cache metadata for eye/SANS-related OSDR studies.

Usage:
    python fetch_metadata.py                # fetch all curated studies
    python fetch_metadata.py --search       # also search for new studies
    python fetch_metadata.py OSD-87 OSD-100 # fetch specific studies
"""
import json
import sys
import time
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

from config import (
    OSDR_FILES_URL, OSDR_SEARCH_URL,
    METADATA_DIR, INDEX_FILE, DATA_DIR,
    EYE_SANS_STUDY_IDS, EYE_SANS_KEYWORDS,
)


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


def fetch_study_details(study_id: str) -> dict:
    """Fetch rich study metadata (title, description, assay type, etc.) from the search API."""
    encoded = urllib.parse.quote(study_id)
    url = f"{OSDR_SEARCH_URL}?ffield=Accession&fvalue={encoded}&size=1&from=0"
    try:
        data = fetch_json(url)
        hits = data.get("hits", {}).get("hits", [])
        if hits:
            return hits[0].get("_source", {})
    except Exception:
        pass
    return {}


def fetch_study_metadata(study_id: str) -> dict | None:
    """Fetch all file metadata for a single study."""
    # API requires numeric ID, e.g. "87" not "OSD-87"
    numeric_id = study_id.replace("OSD-", "").strip()
    url = f"{OSDR_FILES_URL}/{numeric_id}/?page=1&size=500&all_files=true"
    try:
        data = fetch_json(url)
        studies = data.get("studies", {})
        if not studies:
            print(f"  [!] No data returned for {study_id}")
            return None
        # Key is always the full "OSD-XX" form in the response
        study_data = studies.get(study_id, {})
        details = fetch_study_details(study_id)
        return {
            "study_id": study_id,
            "title": details.get("Study Title", details.get("Project Title", "")),
            "description": details.get("Study Description", ""),
            "organism": details.get("organism", ""),
            "material_type": details.get("Material Type", ""),
            "assay_measurement": details.get("Study Assay Measurement Type", ""),
            "assay_platform": details.get("Study Assay Technology Platform", ""),
            "assay_technology": details.get("Study Assay Technology Type", ""),
            "study_factor": details.get("Study Factor Name", ""),
            "mission": details.get("Mission", {}),
            "project_type": details.get("Project Type", ""),
            "flight_program": details.get("Flight Program", ""),
            "publication_title": details.get("Study Publication Title", ""),
            "publication_authors": details.get("Study Publication Author List", ""),
            "managing_center": details.get("Managing NASA Center", ""),
            "details": details,
            "file_count": study_data.get("file_count", 0),
            "files": study_data.get("study_files", []),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    except Exception as e:
        print(f"  [!] Failed to fetch {study_id}: {e}")
        return None


def search_studies(keyword: str, size: int = 20) -> list[str]:
    """Search OSDR for studies by title keyword, return OSD-* accession IDs."""
    encoded = urllib.parse.quote(keyword)
    url = f"{OSDR_SEARCH_URL}?ffield=Study+Title&fvalue={encoded}&size={size}&from=0"
    try:
        data = fetch_json(url)
        hits = data.get("hits", {}).get("hits", [])
        ids = []
        for h in hits:
            acc = h.get("_source", {}).get("Accession", "")
            if acc.startswith("OSD-"):
                ids.append(acc)
        return ids
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


def fetch_studies(study_ids: list[str], index: dict) -> dict:
    new_count = 0
    for study_id in study_ids:
        if study_id in index:
            print(f"  [=] {study_id} already cached ({index[study_id]['file_count']} files)")
            continue
        print(f"  [>] Fetching {study_id} ...")
        meta = fetch_study_metadata(study_id)
        if meta:
            save_study(study_id, meta)
            index[study_id] = {
                "file_count": meta["file_count"],
                "fetched_at": meta["fetched_at"],
            }
            print(f"  [+] {study_id}: {meta['file_count']} files")
            new_count += 1
        time.sleep(0.5)  # be polite to the API
    return index


def main():
    parser = argparse.ArgumentParser(description="Fetch OSDR eye/SANS metadata")
    parser.add_argument("study_ids", nargs="*", help="Specific OSD study IDs to fetch")
    parser.add_argument("--search", action="store_true", help="Search OSDR for additional studies")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if already cached")
    args = parser.parse_args()

    index = {} if args.force else load_index()

    if args.study_ids:
        target_ids = [s.upper() if s.upper().startswith("OSD-") else f"OSD-{s}" for s in args.study_ids]
    else:
        target_ids = list(EYE_SANS_STUDY_IDS)

    if args.search:
        print("\nSearching OSDR for additional eye/SANS studies...")
        discovered = set()
        for kw in EYE_SANS_KEYWORDS:
            found = search_studies(kw)
            new = [x for x in found if x not in target_ids]
            if new:
                print(f"  [{kw}] found: {', '.join(new)}")
            discovered.update(new)
        if discovered:
            print(f"\nDiscovered {len(discovered)} additional studies: {', '.join(sorted(discovered))}")
            target_ids = list(set(target_ids) | discovered)

    print(f"\nFetching metadata for {len(target_ids)} studies...")
    index = fetch_studies(target_ids, index)
    save_index(index)

    print(f"\nDone. {len(index)} studies cached in {METADATA_DIR}")


if __name__ == "__main__":
    main()
