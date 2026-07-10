export default function Sidebar({ conversations, activeId, onSelect, onNew, onDelete }) {
  return (
    <aside className="sidebar">
      <button className="new-chat" onClick={onNew}>+ New chat</button>
      <nav className="conv-list">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={"conv-item" + (c.id === activeId ? " active" : "")}
            onClick={() => onSelect(c.id)}
          >
            <span className="conv-title">{c.title || "New chat"}</span>
            <button
              className="conv-del"
              title="Delete"
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
            >
              ×
            </button>
          </div>
        ))}
        {!conversations.length && <p className="muted">No conversations yet.</p>}
      </nav>
      <footer className="sidebar-foot muted">History is saved in your browser.</footer>
    </aside>
  );
}
