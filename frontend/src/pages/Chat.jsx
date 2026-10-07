import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { http } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import MessageView from "@/components/MessageView";
import {
  Plus, Send, Loader2, Trash2, Pencil, LogOut, Database, ChevronRight, Check, X
} from "lucide-react";

const SPLUNK = "#F24E1E";
const BQ = "#007AFF";

function Sidebar({ chats, currentId, onNew, onDelete, onRename }) {
  const { user, logout } = useAuth();
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");

  return (
    <aside className="w-[280px] shrink-0 border-r border-white/10 bg-[#070707] flex flex-col h-screen">
      <div className="px-5 py-5 border-b border-white/10">
        <div className="flex items-center gap-2 mb-5">
          <span className="inline-block w-2 h-2 bg-[#F24E1E]" />
          <span className="font-mono text-[11px] tracking-[0.25em] text-neutral-300">INSIGHTLENS</span>
        </div>
        <button
          onClick={onNew}
          data-testid="new-chat-btn"
          className="w-full flex items-center justify-between gap-2 bg-white text-black px-3 py-2.5 text-sm font-medium hover:bg-neutral-200"
          style={{ transitionProperty: "background-color" }}
        >
          <span className="flex items-center gap-2"><Plus className="w-4 h-4" /> New analysis</span>
          <span className="font-mono text-[10px] text-neutral-500">⌘N</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2" data-testid="chat-history-list">
        <div className="font-mono text-[10px] tracking-widest text-neutral-600 px-3 py-2">HISTORY</div>
        {chats.length === 0 && (
          <div className="px-3 py-6 font-mono text-xs text-neutral-600">No conversations yet.</div>
        )}
        {chats.map((c) => {
          const active = c.chat_id === currentId;
          const editing = editingId === c.chat_id;
          return (
            <div
              key={c.chat_id}
              data-testid={`chat-item-${c.chat_id}`}
              className={`group flex items-center gap-1 px-2 py-2 border-l-2 ${active ? "bg-white/[0.04] border-[#F24E1E]" : "border-transparent hover:bg-white/[0.02]"}`}
              style={{ transitionProperty: "background-color, border-color" }}
            >
              {editing ? (
                <>
                  <input
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    autoFocus
                    className="flex-1 bg-black border border-white/30 font-mono text-xs text-white px-2 py-1 focus:outline-none focus:border-white"
                  />
                  <button onClick={() => { onRename(c.chat_id, editValue); setEditingId(null); }} className="p-1 hover:text-[#00E676]">
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => setEditingId(null)} className="p-1 hover:text-[#E63946]">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </>
              ) : (
                <>
                  <Link
                    to={`/chat/${c.chat_id}`}
                    className="flex-1 font-mono text-xs truncate text-neutral-300 hover:text-white"
                    data-testid={`chat-link-${c.chat_id}`}
                    style={{ transitionProperty: "color" }}
                  >
                    {c.title}
                  </Link>
                  <button
                    onClick={() => { setEditingId(c.chat_id); setEditValue(c.title); }}
                    className="p-1 opacity-0 group-hover:opacity-100 text-neutral-500 hover:text-white"
                    data-testid={`chat-rename-${c.chat_id}`}
                  >
                    <Pencil className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => onDelete(c.chat_id)}
                    className="p-1 opacity-0 group-hover:opacity-100 text-neutral-500 hover:text-[#E63946]"
                    data-testid={`chat-delete-${c.chat_id}`}
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </>
              )}
            </div>
          );
        })}
      </div>

      <div className="border-t border-white/10 p-3">
        <Link
          to="/connections"
          data-testid="connections-link"
          className="flex items-center justify-between px-3 py-2 border border-white/10 hover:border-white/30 mb-3"
          style={{ transitionProperty: "border-color" }}
        >
          <span className="flex items-center gap-2 font-mono text-xs text-neutral-300">
            <Database className="w-3.5 h-3.5" /> CONNECTIONS
          </span>
          <ChevronRight className="w-3.5 h-3.5 text-neutral-500" />
        </Link>
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="w-7 h-7 bg-neutral-800 border border-white/10 flex items-center justify-center font-mono text-[11px]">
            {(user?.name || user?.email || "?")[0].toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-mono text-[11px] text-neutral-200 truncate" data-testid="user-name">{user?.name || user?.email}</div>
            <div className="font-mono text-[10px] text-neutral-500 truncate">{user?.email}</div>
          </div>
          <button onClick={logout} data-testid="logout-btn" className="p-1.5 text-neutral-500 hover:text-white" style={{ transitionProperty: "color" }}>
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}

function SourceChip({ id, active, onToggle }) {
  const color = id === "splunk" ? SPLUNK : BQ;
  return (
    <button
      type="button"
      onClick={() => onToggle(id)}
      data-testid={`source-chip-${id}`}
      className={`font-mono text-[10px] uppercase tracking-widest px-2.5 py-1 border ${active ? "" : "opacity-40"}`}
      style={{ borderColor: color, color: active ? color : "#737373", transitionProperty: "opacity" }}
    >
      {id === "splunk" ? "SPLUNK" : "BIGQUERY"}
    </button>
  );
}

function Composer({ onSend, busy }) {
  const [text, setText] = useState("");
  const [sources, setSources] = useState(["splunk", "bigquery"]);

  const toggle = (s) => setSources((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const submit = (e) => {
    e.preventDefault();
    if (!text.trim() || busy || sources.length === 0) return;
    onSend(text.trim(), sources);
    setText("");
  };

  return (
    <form
      onSubmit={submit}
      className="sticky bottom-0 border-t border-white/10 bg-[#050505]/90 backdrop-blur-xl px-6 py-4"
      data-testid="chat-composer"
    >
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-2 mb-2">
          <span className="font-mono text-[10px] text-neutral-500 tracking-widest">SOURCES</span>
          <SourceChip id="splunk" active={sources.includes("splunk")} onToggle={toggle} />
          <SourceChip id="bigquery" active={sources.includes("bigquery")} onToggle={toggle} />
        </div>
        <div className="flex items-end gap-2 border border-white/15 bg-[#0f0f0f] focus-within:border-white/40" style={{ transitionProperty: "border-color" }}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { submit(e); } }}
            rows={2}
            placeholder="Ask about checkout rate, cart abandonment, revenue by market, funnel dropoff…"
            data-testid="chat-input"
            className="flex-1 bg-transparent px-4 py-3 text-sm text-white placeholder-neutral-600 focus:outline-none resize-none font-mono"
          />
          <button
            type="submit"
            disabled={busy || !text.trim() || sources.length === 0}
            data-testid="chat-send-btn"
            className="m-2 bg-white text-black px-3 py-2 disabled:opacity-40 hover:bg-neutral-200"
            style={{ transitionProperty: "background-color" }}
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <div className="font-mono text-[10px] text-neutral-600 mt-2">
          Returns markdown + tables + charts. Enter to send · Shift+Enter for newline.
        </div>
      </div>
    </form>
  );
}

function EmptyState({ onPick }) {
  const suggestions = [
    "Why was checkout rate down yesterday in the US market?",
    "Compare revenue across markets for the last 14 days.",
    "Which payment methods have the worst success rate?",
    "Where are shoppers abandoning the checkout funnel?",
  ];
  return (
    <div className="max-w-3xl mx-auto px-6 py-16" data-testid="chat-empty-state">
      <div className="font-mono text-[11px] tracking-[0.3em] text-neutral-500 mb-4">// INSIGHTLENS / NEW SESSION</div>
      <h1 className="font-display text-4xl lg:text-5xl font-black mb-3">What should we investigate?</h1>
      <p className="text-neutral-400 max-w-xl mb-10">
        Ask a question. We'll query the selected sources, run the analysis, and write you a report with charts and a downloadable PDF.
      </p>
      <div className="grid sm:grid-cols-2 gap-3">
        {suggestions.map((s, i) => (
          <button
            type="button"
            key={i}
            data-testid={`suggestion-${i}`}
            onClick={() => onPick(s)}
            className="text-left border border-white/10 hover:border-white/40 p-4 group bg-transparent"
            style={{ transitionProperty: "border-color" }}
          >
            <div
              className="font-mono text-[10px] text-neutral-500 tracking-widest mb-2 group-hover:text-[#F24E1E]"
              style={{ transitionProperty: "color" }}
            >
              EXAMPLE / {String(i + 1).padStart(2, "0")}
            </div>
            <div className="text-sm text-neutral-200">{s}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Chat() {
  const { chatId } = useParams();
  const nav = useNavigate();
  const [chats, setChats] = useState([]);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);
  const skipLoadRef = useRef(null);

  const loadChats = async () => {
    const { data } = await http.get("/chats");
    setChats(data.chats);
    return data.chats;
  };

  const loadMessages = async (id) => {
    if (!id) { setMessages([]); return; }
    try {
      const { data } = await http.get(`/chats/${id}/messages`);
      setMessages(data.messages);
    } catch { setMessages([]); }
  };

  useEffect(() => { loadChats(); }, []);
  useEffect(() => {
    if (skipLoadRef.current === chatId) {
      skipLoadRef.current = null;
      return;
    }
    loadMessages(chatId);
  }, [chatId]);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

  const createNew = async () => {
    const { data } = await http.post("/chats", {});
    await loadChats();
    nav(`/chat/${data.chat_id}`);
  };

  const onDelete = async (id) => {
    await http.delete(`/chats/${id}`);
    const next = await loadChats();
    if (id === chatId) {
      if (next.length) nav(`/chat/${next[0].chat_id}`); else nav("/");
    }
  };

  const onRename = async (id, title) => {
    await http.patch(`/chats/${id}`, { title: title || "Untitled" });
    await loadChats();
  };

  const onSend = async (content, sources) => {
    let activeId = chatId;
    const isNew = !activeId;
    if (isNew) {
      const { data } = await http.post("/chats", {});
      activeId = data.chat_id;
      skipLoadRef.current = activeId;
      await loadChats();
      nav(`/chat/${activeId}`, { replace: true });
    }
    // optimistic user message
    const temp = { message_id: `tmp_${Date.now()}`, role: "user", content, sources, artifacts: [], created_at: new Date().toISOString() };
    setMessages((m) => (isNew ? [temp] : [...m, temp]));
    setBusy(true);
    try {
      const { data } = await http.post(`/chats/${activeId}/messages`, { content, sources });
      setMessages((m) => [...m.filter((x) => x.message_id !== temp.message_id), data.user_message, data.assistant_message]);
      loadChats();
    } catch (e) {
      setMessages((m) => m.filter((x) => x.message_id !== temp.message_id));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-[#050505] text-white grain">
      <Sidebar
        chats={chats}
        currentId={chatId}
        onNew={createNew}
        onDelete={onDelete}
        onRename={onRename}
      />
      <main className="flex-1 flex flex-col h-screen">
        <div ref={scrollRef} className="flex-1 overflow-y-auto" data-testid="chat-transcript">
          {messages.length === 0 && !busy ? (
            <EmptyState onPick={(text) => onSend(text, ["splunk", "bigquery"])} />
          ) : (
            <div className="max-w-3xl mx-auto px-6 py-4">
              {messages.map((m) => <MessageView key={m.message_id} msg={m} />)}
              {busy && (
                <div className="py-6 flex items-center gap-3 font-mono text-xs text-neutral-500" data-testid="chat-loading">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Querying sources & synthesizing report…
                </div>
              )}
            </div>
          )}
        </div>
        <Composer onSend={onSend} busy={busy} />
      </main>
    </div>
  );
}
