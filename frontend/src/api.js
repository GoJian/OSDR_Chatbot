// Thin client for the FastAPI backend.
//
// Paths are RELATIVE (no leading slash) so the app works both at the site root
// and behind a path prefix like OOD's /node/datahive/8077/ per-user proxy.
// `API` resolves against the page URL, which the OOD proxy strips before it
// reaches the backend.
const API = new URL("api/", document.baseURI).href;

export async function fetchModels() {
  const r = await fetch(API + "models");
  if (!r.ok) throw new Error("models unavailable");
  return r.json();
}

export async function fetchStudies() {
  const r = await fetch(API + "studies");
  return r.json();
}

// Stream a chat answer. Calls onSources(ids, model) once, then onToken(t) per
// token, then onDone(). Parses the SSE stream from POST /api/chat manually
// (EventSource only supports GET).
export async function streamChat({ message, history, model }, { onSources, onToken, onError, onDone }) {
  const resp = await fetch(API + "chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, model }),
  });
  if (!resp.ok || !resp.body) {
    onError?.(`request failed (${resp.status})`);
    onDone?.();
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line.
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      let event = "message";
      let data = "";
      for (const line of evt.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      const parsed = JSON.parse(data);
      if (event === "sources") onSources?.(parsed.studies, parsed.model);
      else if (event === "token") onToken?.(parsed);
      else if (event === "error") onError?.(parsed);
      else if (event === "done") onDone?.();
    }
  }
  onDone?.();
}
