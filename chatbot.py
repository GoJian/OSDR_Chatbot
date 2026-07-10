#!/usr/bin/env python3
"""OSDR ChatBot — CLI front end over the shared RAG backend.

Usage:
    python chatbot.py
    python chatbot.py --model gemma4
    python chatbot.py --list-studies
"""
import json
import argparse

from backend.config import (
    OLLAMA_MODEL, OLLAMA_FALLBACK_MODEL, INDEX_FILE, RAG_TOP_K,
)
from backend import rag, ollama_client


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {}


def chat_loop(model: str, index: dict):
    print("\n OSDR ChatBot (RAG)")
    print(f" Model: {model} | Studies indexed: {len(index)}")
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
            print(f"\nIndexed studies ({len(index)}):")
            for sid, data in sorted(index.items()):
                print(f"  {sid}: {data.get('file_count', 0)} files — {data.get('title','')[:60]}")
            print()
            continue

        context, sources = rag.build_context(user_input, RAG_TOP_K)
        messages = [{"role": "system", "content": rag.SYSTEM_PROMPT}]
        if context:
            messages.append({"role": "system", "content": f"OSDR context:\n{context}"})
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        print("\nAssistant: ", end="", flush=True)
        response = ""
        try:
            for token in ollama_client.chat_stream(model, messages):
                print(token, end="", flush=True)
                response += token
            print()
            if sources:
                print(f"Sources: {', '.join(sources)}")
        except Exception as e:
            print(f"\n[Error] {e}")
            continue

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})
        if len(history) > 20:
            history = history[-20:]
        print()


def main():
    parser = argparse.ArgumentParser(description="OSDR ChatBot (RAG CLI)")
    parser.add_argument("--model", default=OLLAMA_MODEL, help=f"Ollama model (default: {OLLAMA_MODEL})")
    parser.add_argument("--list-studies", action="store_true", help="List cached studies and exit")
    args = parser.parse_args()

    index = load_index()

    if args.list_studies:
        if not index:
            print("No studies cached. Run: python -m backend.fetch_metadata")
        else:
            print(f"Cached studies ({len(index)}):")
            for sid, data in sorted(index.items()):
                print(f"  {sid}: {data.get('file_count', 0)} files  [{data.get('fetched_at', '')}]")
        return

    if not index:
        print("[!] No metadata cached. Run: python -m backend.fetch_metadata")
        print("    then build the index: python -m backend.ingest")
        return

    ok, resolved = ollama_client.resolve_model(args.model)
    if not ok:
        print(f"[!] {resolved}")
        ok, resolved = ollama_client.resolve_model(OLLAMA_FALLBACK_MODEL)
        if ok:
            print(f"[>] Falling back to {resolved}")
        else:
            print(f"[!] {resolved}")
            print("Start ollama and pull a model, e.g.: ollama pull gemma4")
            return

    chat_loop(resolved, index)


if __name__ == "__main__":
    main()
