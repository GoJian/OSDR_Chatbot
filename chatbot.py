#!/usr/bin/env python3
"""
OSDR Eye/SANS ChatBot — powered by ollama + local metadata cache.

Usage:
    python chatbot.py
    python chatbot.py --model gemma4
    python chatbot.py --list-studies
"""
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

from config import (
    OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_FALLBACK_MODEL,
    METADATA_DIR, INDEX_FILE, EYE_SANS_KEYWORDS,
)

SYSTEM_PROMPT = """You are an expert scientific assistant specializing in NASA's Open Science Data Repository (OSDR) and space medicine — specifically Space Associated Neuro-ocular Syndrome (SANS) and spaceflight effects on the eye.

You have access to metadata from OSDR studies related to eye health, retinal changes, intraocular pressure, optic disc edema, and neuro-ocular effects of microgravity.

When answering:
- Cite specific OSD study IDs (e.g. OSD-87, OSD-679) when relevant
- Distinguish between human astronaut studies and rodent models
- Note whether data comes from actual spaceflight vs. ground-based analogs (head-down tilt, hindlimb unloading)
- Be precise about assay types (RNA-seq, proteomics, histology, IOP measurements, etc.)
- If you don't know, say so — do not fabricate study details

OSDR context provided below comes from fetched metadata files."""


def load_all_metadata() -> dict[str, dict]:
    """Load all cached study metadata from data/metadata/."""
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


def build_context(studies: dict[str, dict], query: str) -> str:
    """Build a context string from study metadata relevant to the query."""
    query_lower = query.lower()

    scored = []
    for sid, data in studies.items():
        files = data.get("files", [])
        text_blob = " ".join([
            sid,
            data.get("title", ""),
            data.get("description", ""),
            data.get("material_type", ""),
            data.get("assay_measurement", ""),
            data.get("publication_title", ""),
        ] + [
            f"{f.get('file_name','')} {f.get('category','')} {f.get('subcategory','')}"
            for f in files
        ]).lower()
        kw_score = sum(1 for kw in EYE_SANS_KEYWORDS if kw.lower() in text_blob)
        q_score = sum(1 for word in query_lower.split() if len(word) > 3 and word in text_blob)
        scored.append((kw_score + q_score * 3, sid, data))

    scored.sort(reverse=True)

    lines = [f"OSDR metadata for {len(studies)} eye/SANS-related studies:\n"]
    for _, sid, data in scored[:8]:
        files = data.get("files", [])
        categories = sorted({f.get("category", "") for f in files if f.get("category")})
        mission = data.get("mission", {})
        mission_str = mission.get("Name", "") if isinstance(mission, dict) else str(mission)
        lines.append(
            f"\n[{sid}] {data.get('title', 'No title')}\n"
            f"  Organism: {data.get('organism','')} | Tissue: {data.get('material_type','')}\n"
            f"  Assay: {data.get('assay_measurement','')} / {data.get('assay_platform','')}\n"
            f"  Factor: {data.get('study_factor','')} | Mission: {mission_str}\n"
            f"  Files ({data.get('file_count',0)}): {', '.join(categories[:5])}\n"
            f"  Description: {data.get('description','')[:200]}"
        )

    return "\n".join(lines)


def check_ollama(model: str) -> tuple[bool, str]:
    """Check if ollama is running and the model is available."""
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        available = [m["name"] for m in data.get("models", [])]
        # exact match or prefix match
        for m in available:
            if m == model or m.startswith(model.split(":")[0]):
                return True, m
        return False, f"Model '{model}' not found. Available: {', '.join(available)}"
    except Exception as e:
        return False, f"Ollama not reachable at {OLLAMA_HOST}: {e}"


def stream_response(model: str, messages: list[dict]) -> str:
    """Stream a chat response from ollama, printing tokens as they arrive."""
    payload = json.dumps({"model": model, "messages": messages, "stream": True}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    full_response = ""
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                print(token, end="", flush=True)
                full_response += token
                if chunk.get("done"):
                    break
            except json.JSONDecodeError:
                pass
    print()  # newline after streaming
    return full_response


def chat_loop(model: str, studies: dict[str, dict]):
    print(f"\n OSDR Eye/SANS ChatBot")
    print(f" Model: {model} | Studies loaded: {len(studies)}")
    print(" Type 'quit' or Ctrl+C to exit, 'studies' to list loaded studies\n")

    history: list[dict] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        if user_input.lower() == "studies":
            if not studies:
                print("No studies loaded. Run: python fetch_metadata.py")
            else:
                print(f"\nLoaded studies ({len(studies)}):")
                for sid, data in sorted(studies.items()):
                    print(f"  {sid}: {data.get('file_count', 0)} files")
            print()
            continue

        # Build context from metadata
        context = build_context(studies, user_input) if studies else ""

        # Construct messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if context:
            messages.append({"role": "system", "content": f"OSDR Metadata:\n{context}"})
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        print("\nAssistant: ", end="", flush=True)
        try:
            response = stream_response(model, messages)
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            # Keep last 10 turns to avoid context overflow
            if len(history) > 20:
                history = history[-20:]
        except urllib.error.URLError as e:
            print(f"\n[Error] Could not reach ollama: {e}")
        except Exception as e:
            print(f"\n[Error] {e}")
        print()


def main():
    parser = argparse.ArgumentParser(description="OSDR Eye/SANS ChatBot")
    parser.add_argument("--model", default=OLLAMA_MODEL, help=f"Ollama model (default: {OLLAMA_MODEL})")
    parser.add_argument("--list-studies", action="store_true", help="List cached studies and exit")
    args = parser.parse_args()

    studies = load_all_metadata()

    if args.list_studies:
        if not studies:
            print("No studies cached. Run: python fetch_metadata.py")
        else:
            print(f"Cached studies ({len(studies)}):")
            for sid, data in sorted(studies.items()):
                print(f"  {sid}: {data.get('file_count', 0)} files  [{data.get('fetched_at', '')}]")
        return

    if not studies:
        print("[!] No metadata cached. Fetching now...")
        import subprocess, sys
        subprocess.run([sys.executable, "fetch_metadata.py"], check=False)
        studies = load_all_metadata()

    # Resolve model
    model = args.model
    ok, msg = check_ollama(model)
    if not ok:
        print(f"[!] {msg}")
        ok2, msg2 = check_ollama(OLLAMA_FALLBACK_MODEL)
        if ok2:
            print(f"[>] Falling back to {OLLAMA_FALLBACK_MODEL}")
            model = msg2  # msg2 is the resolved model name on success
        else:
            print(f"[!] {msg2}")
            print("Please start ollama and pull a model: ollama pull gemma4")
            return
    else:
        model = msg  # resolved model name

    chat_loop(model, studies)


if __name__ == "__main__":
    main()
