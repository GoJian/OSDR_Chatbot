import { useEffect, useRef, useState } from "react";
import { useConversations } from "./hooks/useConversations.js";
import { streamChat, fetchModels } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import Message from "./components/Message.jsx";

export default function App() {
  const {
    conversations, active, activeId, setActiveId,
    createConversation, deleteConversation, updateActive,
  } = useConversations();

  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    fetchModels()
      .then((d) => {
        setModels(d.models || []);
        const preferred = (d.models || []).find((m) => m.startsWith(d.default)) || d.models?.[0];
        setModel(preferred || "");
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [active?.messages, busy]);

  async function send(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);

    // Snapshot history BEFORE appending, for the API call.
    const history = (active?.messages || []).map((m) => ({ role: m.role, content: m.content }));

    updateActive((msgs) => [
      ...msgs,
      { role: "user", content: text },
      { role: "assistant", content: "", sources: [] },
    ]);

    await streamChat(
      { message: text, history, model },
      {
        onSources: (studies) =>
          updateActive((msgs) => patchLast(msgs, (m) => ({ ...m, sources: studies }))),
        onToken: (t) =>
          updateActive((msgs) => patchLast(msgs, (m) => ({ ...m, content: m.content + t }))),
        onError: (err) =>
          updateActive((msgs) => patchLast(msgs, (m) => ({ ...m, content: m.content + `\n\n[error] ${err}` }))),
        onDone: () => setBusy(false),
      }
    );
  }

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={createConversation}
        onDelete={deleteConversation}
      />

      <main className="chat">
        <header className="chat-header">
          <div>
            <strong>OSDR ChatBot</strong>
            <span className="subtitle"> · NASA Open Science Data Repository · RAG</span>
          </div>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {models.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </header>

        <div className="messages" ref={scrollRef}>
          {!active?.messages.length && (
            <div className="empty">
              <p>Ask about any of NASA's OSDR studies.</p>
              <p className="hint">e.g. "Which studies measured intraocular pressure during spaceflight?"</p>
            </div>
          )}
          {active?.messages.map((m, i) => (
            <Message key={i} message={m} streaming={busy && i === active.messages.length - 1} />
          ))}
        </div>

        <form className="composer" onSubmit={send}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about OSDR studies…"
            disabled={busy}
            autoFocus
          />
          <button type="submit" disabled={busy || !input.trim()}>
            {busy ? "…" : "Send"}
          </button>
        </form>
      </main>
    </div>
  );
}

// Replace the last message in the list via `fn`.
function patchLast(msgs, fn) {
  if (!msgs.length) return msgs;
  const copy = msgs.slice();
  copy[copy.length - 1] = fn(copy[copy.length - 1]);
  return copy;
}
