import { useEffect, useState } from "react";

// Browser-based history tracking: conversations persist in localStorage, so the
// full chat history survives page reloads and browser restarts.
const KEY = "osdr-conversations";

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
}

function newConversation() {
  return {
    id: crypto.randomUUID(),
    title: "New chat",
    messages: [], // { role: "user" | "assistant", content, sources?: [] }
    createdAt: Date.now(),
  };
}

export function useConversations() {
  const [conversations, setConversations] = useState(load);
  const [activeId, setActiveId] = useState(() => load()[0]?.id ?? null);

  // Persist on every change.
  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(conversations));
  }, [conversations]);

  // Guarantee there is always an active conversation.
  useEffect(() => {
    if (!activeId || !conversations.find((c) => c.id === activeId)) {
      if (conversations.length) setActiveId(conversations[0].id);
      else createConversation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const active = conversations.find((c) => c.id === activeId) || null;

  function createConversation() {
    const conv = newConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    return conv.id;
  }

  function deleteConversation(id) {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (id === activeId) setActiveId((prev) => prev); // effect above will re-home
  }

  // Apply an updater to the active conversation's messages.
  function updateActive(updater) {
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== activeId) return c;
        const messages = updater(c.messages);
        // Title the conversation from its first user message.
        let title = c.title;
        if (title === "New chat") {
          const firstUser = messages.find((m) => m.role === "user");
          if (firstUser) title = firstUser.content.slice(0, 40);
        }
        return { ...c, messages, title };
      })
    );
  }

  return {
    conversations,
    active,
    activeId,
    setActiveId,
    createConversation,
    deleteConversation,
    updateActive,
  };
}
