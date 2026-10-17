import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { ArrowLeft, AlertTriangle, BarChart3, RefreshCw } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { http } from "@/lib/api";

const metricLabels = {
  error_rate_pct: "ERROR RATE",
  orders: "ORDERS",
  revenue_usd: "REVENUE",
  avg_response_time_ms: "AVG RESPONSE",
  checkout_completion_pct: "CHECKOUT COMPLETION",
  avg_order_value_usd: "AVG ORDER VALUE",
  checkout_errors: "CHECKOUT ERRORS",
  checkout_rate_pct: "CHECKOUT RATE",
};

const metricOrder = [
  "error_rate_pct",
  "orders",
  "revenue_usd",
  "avg_response_time_ms",
  "checkout_completion_pct",
  "avg_order_value_usd",
  "checkout_errors",
  "checkout_rate_pct",
];

function displayDate(value) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function metricValue(key, value) {
  if (key === "revenue_usd" || key === "avg_order_value_usd") {
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  if (key.endsWith("_pct")) return `${Number(value).toFixed(1)}%`;
  if (key === "avg_response_time_ms") return `${Math.round(value)} ms`;
  return Math.round(value).toLocaleString();
}

function CheckoutTrends({ source }) {
  if (!source || source.status !== "available") {
    return (
      <section className="border border-white/10 bg-[#0a0a0a] p-5 mb-6">
        <h2 className="font-mono text-[11px] tracking-widest text-neutral-300 mb-3">10-DAY CHECKOUT & ERROR RATES</h2>
        <p className="text-sm text-neutral-400">{source?.error || "Checkout trend data is unavailable."}</p>
      </section>
    );
  }

  const chartData = source.daily.map((row) => ({
    ...row,
    invalid_address_type_rate_pct: row.checkout_starts ? row.invalid_address_type_sessions / row.checkout_starts * 100 : 0,
    invalid_delivery_address_rate_pct: row.checkout_starts ? row.invalid_delivery_address_sessions / row.checkout_starts * 100 : 0,
    invalid_payment_rate_pct: row.checkout_starts ? row.invalid_payment_sessions / row.checkout_starts * 100 : 0,
  }));
  const axisDate = (value) => new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const rateTooltip = (value) => `${Number(value).toFixed(1)}%`;
  const commonChartProps = {
    data: chartData,
    margin: { top: 8, right: 12, left: -18, bottom: 0 },
  };

  return (
    <section className="border border-white/10 bg-[#0a0a0a] p-5 mb-6">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <div>
          <h2 className="font-mono text-[11px] tracking-widest text-neutral-300">10-DAY CHECKOUT & ERROR RATES</h2>
          <p className="text-xs text-neutral-500 mt-2">{displayDate(source.period.start)} – {displayDate(source.period.end)} · latest available checkout data</p>
        </div>
        <div className="flex flex-wrap gap-4 font-mono text-[10px] text-neutral-400">
          <span>CHECKOUT {source.current_metrics.checkout_rate_pct.toFixed(1)}%</span>
          <span>ERROR SESSIONS {source.current_metrics.error_rate_pct.toFixed(1)}%</span>
          <span>{source.current_metrics.error_events.toLocaleString()} ERROR EVENTS</span>
        </div>
      </div>
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="border border-white/5 p-4">
          <h3 className="font-mono text-[10px] tracking-widest text-neutral-400 mb-4">CHECKOUT COMPLETION RATE</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart {...commonChartProps}>
                <CartesianGrid stroke="#262626" strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={axisDate} stroke="#737373" tick={{ fill: "#a3a3a3", fontSize: 10 }} />
                <YAxis tickFormatter={rateTooltip} stroke="#737373" tick={{ fill: "#a3a3a3", fontSize: 10 }} />
                <Tooltip labelFormatter={axisDate} formatter={rateTooltip} contentStyle={{ background: "#111", border: "1px solid #333" }} />
                <Line type="monotone" dataKey="checkout_rate_pct" name="Checkout rate" stroke="#00E676" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-neutral-600 mt-2">Completed checkout sessions ÷ checkout-start sessions for each day.</p>
        </div>
        <div className="border border-white/5 p-4">
          <h3 className="font-mono text-[10px] tracking-widest text-neutral-400 mb-4">ERROR SESSION RATE BY TYPE</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart {...commonChartProps}>
                <CartesianGrid stroke="#262626" strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={axisDate} stroke="#737373" tick={{ fill: "#a3a3a3", fontSize: 10 }} />
                <YAxis tickFormatter={rateTooltip} stroke="#737373" tick={{ fill: "#a3a3a3", fontSize: 10 }} />
                <Tooltip labelFormatter={axisDate} formatter={rateTooltip} contentStyle={{ background: "#111", border: "1px solid #333" }} />
                <Legend wrapperStyle={{ fontSize: 10, color: "#a3a3a3" }} />
                <Line type="monotone" dataKey="error_rate_pct" name="Any tracked error" stroke="#F24E1E" strokeWidth={2} dot={{ r: 2 }} connectNulls />
                <Line type="monotone" dataKey="invalid_address_type_rate_pct" name="Invalid address type" stroke="#FF9F0A" dot={{ r: 2 }} connectNulls />
                <Line type="monotone" dataKey="invalid_delivery_address_rate_pct" name="Invalid delivery address" stroke="#AF52DE" dot={{ r: 2 }} connectNulls />
                <Line type="monotone" dataKey="invalid_payment_rate_pct" name="Invalid payment" stroke="#64D2FF" dot={{ r: 2 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-neutral-600 mt-2">Distinct sessions with each error ÷ checkout-start sessions for each day.</p>
        </div>
      </div>
    </section>
  );
}

function SourceDashboard({ source }) {
  const label = source.source === "local_logs"
    ? "LOCAL CSV"
    : source.source === "bigquery_checkout_errors"
      ? "BIGQUERY — CHECKOUT ERRORS"
      : "BIGQUERY — ORDERS";
  const keys = source.current_metrics
    ? metricOrder.filter((key) => key in source.current_metrics)
    : [];

  return (
    <section className="border border-white/10 bg-[#0a0a0a] mb-6" data-testid={`dashboard-source-${source.source}`}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-white/10">
        <h2 className="font-mono text-[11px] tracking-widest text-neutral-300">{label}</h2>
        <span className={`font-mono text-[10px] tracking-widest uppercase ${
          source.status === "available" ? "text-[#00E676]" : source.status === "no_data" ? "text-[#FFD60A]" : "text-[#F24E1E]"
        }`}>
          {source.status.replace("_", " ")}
        </span>
      </div>
      {source.status !== "available" ? (
        <p className="px-5 py-4 text-sm text-neutral-400">{source.error}</p>
      ) : (
        <div className="p-5">
          <div className="flex flex-wrap gap-x-5 gap-y-2 mb-5 font-mono text-[10px] tracking-widest text-neutral-500">
            <span>DATA THROUGH {displayDate(source.latest_data_date).toUpperCase()}</span>
            <span>{displayDate(source.period.start)} – {displayDate(source.period.end)}</span>
            <span>VS {displayDate(source.baseline_period.start)} – {displayDate(source.baseline_period.end)}</span>
          </div>
          {source.coverage_note && (
            <p className="text-xs text-neutral-500 mb-5">{source.coverage_note}</p>
          )}
          {(!source.current_available && source.current_available !== undefined) && (
            <div className="border border-[#FFD60A]/30 bg-[#FFD60A]/5 p-4 mb-5 text-sm text-[#FFD60A]">
              The selected window has incomplete daily data; no anomaly comparison was made.
            </div>
          )}
          {!source.baseline_available && (
            <div className="border border-[#FFD60A]/30 bg-[#FFD60A]/5 p-4 mb-5 text-sm text-[#FFD60A]">
              The previous period has incomplete daily data; no anomaly comparison was made.
            </div>
          )}
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6" aria-label={`${label} metrics`}>
            {keys.map((key) => (
              <div key={key} className="border border-white/10 p-4">
                <div className="font-mono text-[10px] tracking-widest text-neutral-500 mb-3">{metricLabels[key]}</div>
                <div className="font-display text-2xl font-bold">{metricValue(key, source.current_metrics[key])}</div>
                <div className="font-mono text-[10px] text-neutral-600 mt-2">
                  PREVIOUS: {metricValue(key, source.baseline_metrics[key])}
                </div>
              </div>
            ))}
          </div>

          {source.source === "bigquery_checkout_errors" && (
            <div className="grid md:grid-cols-2 gap-5 mb-6">
              {[
                ["ERRORS BY EVENT", source.current_by_event, "event_name"],
                ["ERRORS BY MARKET", source.current_by_market, "market"],
              ].map(([title, rows, labelKey]) => (
                <div key={title} className="border border-white/10 p-4">
                  <h3 className="font-mono text-[10px] tracking-widest text-neutral-400 mb-3">{title}</h3>
                  {rows.length ? rows.map((row) => (
                    <div key={row[labelKey]} className="flex justify-between gap-4 py-2 border-t border-white/5 text-xs">
                      <span className="text-neutral-300">{row[labelKey]}</span>
                      <span className="font-mono text-white">{row.error_count.toLocaleString()}</span>
                    </div>
                  )) : <p className="text-xs text-neutral-500">No matching events in this period.</p>}
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between mb-3">
            <h3 className="font-mono text-[10px] tracking-widest text-neutral-400">MEASURED ANOMALIES</h3>
            <span className="font-mono text-[10px] text-neutral-500">{source.anomalies.length} DETECTED</span>
          </div>
          {source.anomalies.length ? (
            <div className="grid md:grid-cols-2 gap-3 mb-6">
              {source.anomalies.map((anomaly) => (
                <article key={anomaly.key} className="border border-white/10 p-4">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className={`w-4 h-4 ${anomaly.severity === "high" ? "text-[#F24E1E]" : "text-[#FFD60A]"}`} />
                      <h4 className="font-display text-lg font-bold">{anomaly.metric}</h4>
                    </div>
                    <span className={`font-mono text-[10px] tracking-widest uppercase ${anomaly.severity === "high" ? "text-[#F24E1E]" : "text-[#FFD60A]"}`}>
                      {anomaly.severity}
                    </span>
                  </div>
                  <div className="font-mono text-xs text-neutral-400">
                    {metricValue(anomaly.key, anomaly.baseline)}
                    <span className="px-2 text-neutral-600">→</span>
                    <span className="text-white">{metricValue(anomaly.key, anomaly.current)}</span>
                    <span className="ml-3 text-neutral-500">
                      {anomaly.change_pct === null
                        ? "NEW"
                        : `${anomaly.direction === "increase" ? "+" : "−"}${anomaly.change_pct}%`}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="border border-white/10 p-4 mb-6 text-sm text-neutral-400">
              {source.baseline_available && (source.current_available ?? true)
                ? "No metrics crossed the anomaly thresholds for this period."
                : "No anomaly checks were run because the comparison window is incomplete."}
            </p>
          )}

          <h3 className="font-mono text-[10px] tracking-widest text-neutral-400 mb-3">DAILY ACTIVITY</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead className="text-neutral-500">
                <tr>
                  {[
                    "date",
                    ...(source.source === "local_logs" ? ["events", "errors", "orders", "revenue_usd"] :
                      source.source === "bigquery_checkout_errors" ? ["checkout_errors"] :
                        source.source === "bigquery_checkout_trends"
                          ? ["checkout_starts", "completed_checkouts", "checkout_rate_pct", "error_sessions", "error_events", "error_rate_pct"]
                          : ["orders", "revenue_usd"]),
                  ].map((key) => (
                    <th key={key} className="px-4 py-3 font-normal tracking-widest">{key.replace("_", " ").toUpperCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {source.daily.map((row) => (
                  <tr key={row.date} className="border-t border-white/5 text-neutral-300">
                    <td className="px-4 py-3">{displayDate(row.date)}</td>
                    {(source.source === "local_logs"
                      ? ["events", "errors", "orders", "revenue_usd"]
                      : source.source === "bigquery_checkout_errors" ? ["checkout_errors"]
                        : source.source === "bigquery_checkout_trends"
                          ? ["checkout_starts", "completed_checkouts", "checkout_rate_pct", "error_sessions", "error_events", "error_rate_pct"]
                          : ["orders", "revenue_usd"]
                    ).map((key) => (
                      <td key={key} className="px-4 py-3">
                        {key === "revenue_usd" || key.endsWith("_pct")
                          ? metricValue(key, row[key])
                          : row[key].toLocaleString()}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

export default function Dashboard() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    http.get(`/dashboard/anomalies?days=${days}`)
      .then(({ data: result }) => {
        if (active) setData(result);
      })
      .catch((requestError) => {
        if (active) {
          setData(null);
          setError(requestError.response?.data?.detail || "Could not load anomaly data.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [days]);

  return (
    <div className="min-h-screen bg-[#050505] text-white grain">
      <header className="border-b border-white/10 px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/" className="font-mono text-xs text-neutral-500 hover:text-white flex items-center gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" /> CHAT
          </Link>
          <div className="h-5 w-px bg-white/10" />
          <div className="flex items-center gap-3">
            <img src="/logo.jpg" alt="Lenslight" className="w-7 h-7 object-cover" />
            <div className="font-mono text-sm tracking-[0.25em] text-neutral-200">LENSLIGHT / DASHBOARD</div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-6 mb-8">
          <div>
            <div className="font-mono text-[11px] tracking-[0.3em] text-neutral-500 mb-3">// SIGNAL MONITOR</div>
            <h1 className="font-display text-4xl lg:text-5xl font-black">Recent anomalies.</h1>
            <p className="text-sm text-neutral-400 mt-3 max-w-2xl">
              The AI compares orders, revenue, and checkout error patterns across recent periods. Error and order records are not joined.
            </p>
          </div>
          <label className="font-mono text-[10px] tracking-widest text-neutral-500">
            LOOKBACK WINDOW
            <select
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              className="block mt-2 bg-[#0a0a0a] border border-white/15 px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00E676]"
              data-testid="anomaly-lookback-select"
            >
              {Array.from({ length: 7 }, (_, index) => index + 1).map((value) => (
                <option key={value} value={value}>{value} {value === 1 ? "day" : "days"}</option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <div className="border border-white/10 bg-[#0a0a0a] p-8 text-neutral-400 font-mono text-xs tracking-widest flex items-center gap-3">
            <RefreshCw className="w-4 h-4 animate-spin" /> CHECKING RECENT DATA…
          </div>
        ) : error ? (
          <div role="alert" className="border border-red-500/30 bg-red-500/5 p-5 text-sm text-red-200">
            {error}
          </div>
        ) : data ? (
          <>
            <section className="border border-white/10 bg-[#0a0a0a] mb-6">
              <div className="flex items-center gap-2 px-5 py-4 border-b border-white/10">
                <BarChart3 className="w-4 h-4 text-[#00E676]" />
                <h2 className="font-mono text-[11px] tracking-widest text-neutral-300">GEMINI ANALYSIS</h2>
              </div>
              <div className="px-5 py-4 text-sm text-neutral-300 leading-relaxed prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{data.summary}</ReactMarkdown>
              </div>
            </section>
            <CheckoutTrends source={data.sources.find((source) => source.source === "bigquery_checkout_trends")} />
            <div className="font-mono text-[10px] tracking-widest text-neutral-500 mb-3">
              SOURCE STATUS — {data.sources.filter((source) => source.status === "available").length} OF {data.sources.length} AVAILABLE
            </div>
            {data.sources
              .filter((source) => source.source !== "bigquery_checkout_trends")
              .map((source) => <SourceDashboard key={source.source} source={source} />)}
          </>
        ) : null}
      </main>
    </div>
  );
}
