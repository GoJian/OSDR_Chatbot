"""Shared ollama HTTP client: embeddings, streaming chat, model discovery.

Uses stdlib urllib only — no external HTTP dependency — matching the project's
lightweight, offline-first ethos.
"""
import json
import urllib.request
import urllib.error

from backend.config import OLLAMA_HOST, OLLAMA_EMBED_MODEL


def _post(path: str, payload: dict, timeout: int = 120):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=timeout)


def embed(text: str, model: str = OLLAMA_EMBED_MODEL) -> list[float]:
    """Return the embedding vector for a single piece of text."""
    with _post("/api/embed", {"model": model, "input": text}, timeout=60) as resp:
        data = json.loads(resp.read())
    embeddings = data.get("embeddings") or []
    if not embeddings:
        raise RuntimeError(f"Ollama returned no embedding (model '{model}' installed?)")
    return embeddings[0]


def chat_stream(model: str, messages: list[dict]):
    """Yield content tokens from ollama's streaming chat endpoint."""
    with _post("/api/chat", {"model": model, "messages": messages, "stream": True}) as resp:
        for line in resp:
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
            if chunk.get("done"):
                break


def list_models() -> list[str]:
    """Return the names of all models installed in the local ollama."""
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    return [m["name"] for m in data.get("models", [])]


def resolve_model(model: str) -> tuple[bool, str]:
    """Check ollama is reachable and resolve `model` to an installed name.

    Returns (True, resolved_name) on success, or (False, error_message).
    Matches by exact name or by name prefix (e.g. "gemma4" -> "gemma4:latest").
    """
    try:
        available = list_models()
    except Exception as e:
        return False, f"Ollama not reachable at {OLLAMA_HOST}: {e}"
    for m in available:
        if m == model or m.startswith(model.split(":")[0]):
            return True, m
    return False, f"Model '{model}' not found. Available: {', '.join(available)}"
