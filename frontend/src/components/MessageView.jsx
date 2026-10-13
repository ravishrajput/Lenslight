import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from "recharts";
import { Download, Database, Terminal } from "lucide-react";
import { API } from "@/lib/api";

const SPLUNK = "#F24E1E";
const BQ = "#007AFF";
const LOCAL_LOGS = "#00E676";
const PALETTE = [SPLUNK, BQ, "#00E676", "#FFD60A"];

function Chart({ art }) {
  const { chart_type, x_key, y_keys, data, title } = art;
  const CommonAxis = (
    <>
      <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
      <XAxis dataKey={x_key} stroke="#737373" tick={{ fontFamily: "JetBrains Mono", fontSize: 10 }} />
      <YAxis stroke="#737373" tick={{ fontFamily: "JetBrains Mono", fontSize: 10 }} />
      <Tooltip
        contentStyle={{ background: "#0a0a0a", border: "1px solid #262626", fontFamily: "JetBrains Mono", fontSize: 11, borderRadius: 0 }}
        itemStyle={{ color: "#fff" }}
        cursor={{ fill: "rgba(255,255,255,0.03)" }}
      />
      <Legend wrapperStyle={{ fontFamily: "JetBrains Mono", fontSize: 10, color: "#a3a3a3" }} />
    </>
  );
  return (
    <div className="border border-white/10 bg-[#0a0a0a] p-4" data-testid={`artifact-chart-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="font-mono text-[11px] tracking-widest text-neutral-400 uppercase">{title}</div>
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          {chart_type === "line" ? (
            <LineChart data={data}>
              {CommonAxis}
              {y_keys.map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          ) : (
            <BarChart data={data}>
              {CommonAxis}
              {y_keys.map((k, i) => (
                <Bar key={k} dataKey={k} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function DataTable({ art }) {
  const { rows, title } = art;
  if (!rows || !rows.length) return null;
  const headers = Object.keys(rows[0]);
  return (
    <div className="border border-white/10 bg-[#0a0a0a]" data-testid={`artifact-table-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
        <Database className="w-3.5 h-3.5 text-neutral-400" />
        <span className="font-mono text-[11px] tracking-widest text-neutral-400 uppercase">{title}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full font-mono text-xs">
          <thead>
            <tr className="border-b border-white/10 bg-white/[0.02]">
              {headers.map((h) => (
                <th key={h} className="text-left px-3 py-2 text-neutral-500 font-medium uppercase tracking-wider text-[10px]">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx} className="border-b border-white/5 hover:bg-white/5" style={{ transitionProperty: "background-color" }}>
                {headers.map((h) => (
                  <td key={h} className="px-3 py-2 text-neutral-200">{String(r[h])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Query({ art }) {
  const isSpl = art.language === "spl";
  const isCsv = art.language === "csv";
  const color = isSpl ? SPLUNK : isCsv ? LOCAL_LOGS : BQ;
  return (
    <div className="border border-white/10 bg-[#0a0a0a]" data-testid={`artifact-query-${art.language}`}>
      <div className="px-4 py-2 border-b border-white/10 flex items-center gap-2">
        <Terminal className="w-3.5 h-3.5" style={{ color }} />
        <span className="font-mono text-[11px] tracking-widest uppercase" style={{ color }}>
          {art.title}
        </span>
      </div>
      <pre className="px-4 py-3 font-mono text-xs text-neutral-200 overflow-x-auto whitespace-pre-wrap">{art.code}</pre>
    </div>
  );
}

function PdfButton({ messageId }) {
  const href = `${API}/messages/${messageId}/pdf`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      data-testid={`download-pdf-${messageId}`}
      className="inline-flex items-center gap-2 border border-white/20 px-3 py-2 text-xs font-mono tracking-wider uppercase text-neutral-200 hover:border-white/60 hover:text-white"
      style={{ transitionProperty: "border-color, color" }}
    >
      <Download className="w-3.5 h-3.5" /> Download PDF Report
    </a>
  );
}

export default function MessageView({ msg }) {
  const isUser = msg.role === "user";
  const accentColor = msg.sources?.includes("local_logs") ? LOCAL_LOGS : msg.sources?.includes("splunk") ? SPLUNK : BQ;
  const isStreaming = !!msg._streaming;
  const isPersisted = msg.message_id && !msg.message_id.startsWith("tmp_");

  if (isUser) {
    return (
      <div className="py-5 border-b border-white/5" data-testid={`msg-${msg.message_id}`}>
        <div className="flex items-start gap-4">
          <div className="font-mono text-[10px] tracking-widest text-neutral-500 pt-1 w-16 shrink-0">YOU</div>
          <div className="flex-1">
            <div className="text-neutral-100 text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</div>
            {msg.sources?.length ? (
              <div className="flex gap-1.5 mt-2 flex-wrap">
                {msg.sources.map((s) => (
                  <span key={s} className="font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border"
                        style={{ borderColor: s === "local_logs" ? LOCAL_LOGS : s === "splunk" ? SPLUNK : BQ, color: s === "local_logs" ? LOCAL_LOGS : s === "splunk" ? SPLUNK : BQ }}>
                      {s === "local_logs" ? "LOCAL CSV" : s}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="py-6 border-b border-white/5 bg-white/[0.015]" data-testid={`msg-${msg.message_id}`}>
      <div className="flex items-start gap-4">
        <div className="font-mono text-[10px] tracking-widest pt-1 w-16 shrink-0" style={{ color: accentColor }}>
          REPORT
        </div>
        <div className="flex-1 border-l-2 pl-5" style={{ borderColor: accentColor }}>
          {isStreaming && !msg.content ? (
            <div className="flex items-center gap-2 font-mono text-xs text-neutral-500" data-testid="stream-waiting">
              <span className="inline-block w-1.5 h-1.5 bg-neutral-400 animate-pulse" />
              Querying sources & opening model stream…
            </div>
          ) : (
            <div className="md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-[9px] h-[14px] bg-white align-middle ml-0.5 animate-pulse" data-testid="stream-cursor" />
              )}
            </div>
          )}
          {!isStreaming && msg.artifacts?.length ? (
            <div className="mt-5 space-y-4 snap-in">
              {msg.artifacts.map((art, i) => {
                if (art.type === "chart") return <Chart key={i} art={art} />;
                if (art.type === "table") return <DataTable key={i} art={art} />;
                if (art.type === "query") return <Query key={i} art={art} />;
                return null;
              })}
            </div>
          ) : null}
          {!isStreaming && isPersisted ? (
            <div className="mt-5"><PdfButton messageId={msg.message_id} /></div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
