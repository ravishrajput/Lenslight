import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "@/lib/api";
import { ArrowLeft, Database } from "lucide-react";

export default function Connections() {
  const [conns, setConns] = useState([]);
  useEffect(() => { http.get("/connections").then(({ data }) => setConns(data.connections)); }, []);

  return (
    <div className="min-h-screen bg-[#050505] text-white grain">
      <header className="border-b border-white/10 px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/" data-testid="back-to-chat" className="font-mono text-xs text-neutral-500 hover:text-white flex items-center gap-1.5" style={{ transitionProperty: "color" }}>
            <ArrowLeft className="w-3.5 h-3.5" /> BACK
          </Link>
          <div className="h-5 w-px bg-white/10" />
          <div className="font-mono text-[11px] tracking-[0.3em] text-neutral-300">INSIGHTLENS / CONNECTIONS</div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 py-14">
        <div className="font-mono text-[11px] tracking-[0.3em] text-neutral-500 mb-3">// DATA SOURCES</div>
        <h1 className="font-display text-4xl lg:text-5xl font-black mb-4">Where your reports come from.</h1>
        <p className="text-neutral-400 max-w-xl mb-10">
          These are the systems InsightLens can query. Currently populated with simulated results for safe demos — swap in real credentials when you're ready.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-2 gap-6 stagger">
          {conns.map((c) => (
            <div
              key={c.id}
              data-testid={`connection-card-${c.id}`}
              className="border border-white/10 bg-[#0a0a0a] p-6 hover:border-white/30"
              style={{ transitionProperty: "border-color" }}
            >
              <div className="flex items-start justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 border border-white/15 flex items-center justify-center" style={{ color: c.accent }}>
                    <Database className="w-5 h-5" strokeWidth={1.5} />
                  </div>
                  <div>
                    <div className="font-display text-xl font-bold">{c.name}</div>
                    <div className="font-mono text-[10px] tracking-widest text-neutral-500 uppercase">{c.endpoint}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest">
                  <span className="w-1.5 h-1.5 bg-[#00E676] status-dot" />
                  <span className="text-[#00E676]">{c.status}</span>
                </div>
              </div>
              <p className="text-sm text-neutral-400 mb-5">{c.description}</p>
              <div className="flex items-center justify-between pt-4 border-t border-white/5">
                <span className="font-mono text-[10px] text-neutral-500 uppercase tracking-widest">Mode</span>
                <span
                  className="font-mono text-[10px] uppercase tracking-widest px-2 py-1 border"
                  style={{ borderColor: c.accent, color: c.accent }}
                >
                  {c.mode}
                </span>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
