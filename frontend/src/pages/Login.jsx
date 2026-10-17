import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { formatApiError } from "@/lib/api";
import { ArrowRight, Loader2 } from "lucide-react";

const AUTH_BG =
  "https://images.unsplash.com/photo-1709626011485-6fe000ea2dbc?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA3MDR8MHwxfHNlYXJjaHwzfHxhYnN0cmFjdCUyMGRhdGElMjBnZW9tZXRyeSUyMGRhcmt8ZW58MHx8fHwxNzkxMzk0NDc4fDA&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const nav = useNavigate();
  const { login, register } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register({ email, password, name: name || email.split("@")[0] });
      }
      nav("/", { replace: true });
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-5 bg-[#050505] text-white grain">
      {/* Left: visual */}
      <div className="hidden lg:block lg:col-span-3 relative overflow-hidden border-r border-white/10">
        <img src={AUTH_BG} alt="" className="absolute inset-0 w-full h-full object-cover opacity-60" />
        <div className="absolute inset-0 bg-gradient-to-tr from-black/80 via-black/30 to-black/70" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12">
          <div className="flex items-center gap-2 font-mono text-xs tracking-widest text-neutral-300" data-testid="brand-logo">
            <img src="/logo.jpg" alt="Lenslight logo" className="w-6 h-6 object-cover" />
            <span>LENSLIGHT / v0.1</span>
          </div>
          <div className="max-w-xl">
            <div className="font-mono text-xs tracking-[0.3em] text-neutral-400 mb-4">INTELLIGENCE / SPLUNK · BIGQUERY</div>
            <h1 className="font-display text-5xl lg:text-6xl font-black leading-[0.95] mb-6">
              Ask your data.<br />
              <span className="text-neutral-500">Get a report back.</span>
            </h1>
            <p className="text-neutral-300 text-base max-w-md">
              A ChatGPT-style terminal wired directly into your observability and warehouse stack. Prompt it. Lenslight writes the SQL and SPL for you.
            </p>
          </div>
          <div className="font-mono text-[11px] text-neutral-500 tracking-wider">
            00 / COMMAND CENTER —— SECURE SESSION
          </div>
        </div>
      </div>

      {/* Right: form */}
      <div className="lg:col-span-2 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-sm snap-in">
          <div className="mb-10">
            <div className="font-mono text-[11px] tracking-[0.3em] text-neutral-500 mb-3">
              {mode === "login" ? "// SIGN IN" : "// CREATE ACCOUNT"}
            </div>
            <h2 className="font-display text-3xl font-bold">
              {mode === "login" ? "Welcome back." : "Start analyzing."}
            </h2>
          </div>

          <button
            type="button"
            onClick={() => {
              setMode("login");
              setEmail("demo@insightlens.app");
              setPassword("demo1234");
              setError("");
            }}
            data-testid="fill-demo-creds-btn"
            className="w-full mb-5 flex items-center justify-center gap-2 border border-dashed border-[#F24E1E]/50 py-2.5 text-xs font-mono tracking-widest uppercase text-[#F24E1E] hover:bg-[#F24E1E]/5 hover:border-[#F24E1E]"
            style={{ transitionProperty: "background-color, border-color" }}
          >
            Use demo credentials →
          </button>

          <form onSubmit={submit} className="space-y-3" data-testid="auth-form">
            {mode === "register" && (
              <input
                type="text"
                placeholder="Full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                data-testid="name-input"
                className="w-full bg-[#0f0f0f] border border-white/15 text-white font-mono text-sm px-3 py-3 focus:outline-none focus:border-white/40"
                style={{ transitionProperty: "border-color" }}
              />
            )}
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              data-testid="email-input"
              className="w-full bg-[#0f0f0f] border border-white/15 text-white font-mono text-sm px-3 py-3 focus:outline-none focus:border-white/40"
              style={{ transitionProperty: "border-color" }}
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              data-testid="password-input"
              className="w-full bg-[#0f0f0f] border border-white/15 text-white font-mono text-sm px-3 py-3 focus:outline-none focus:border-white/40"
              style={{ transitionProperty: "border-color" }}
            />

            {error && (
              <div className="font-mono text-xs text-[#E63946] border border-[#E63946]/40 bg-[#E63946]/5 px-3 py-2" data-testid="auth-error">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              data-testid="auth-submit-btn"
              className="w-full flex items-center justify-center gap-2 bg-white text-black font-medium text-sm py-3 hover:bg-neutral-200 disabled:opacity-60"
              style={{ transitionProperty: "background-color" }}
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
              {mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <div className="mt-6 font-mono text-xs text-neutral-500">
            {mode === "login" ? "No account?" : "Have an account?"}{" "}
            <button
              type="button"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
              data-testid="auth-mode-toggle"
              className="text-white underline underline-offset-4 hover:text-[#F24E1E]"
              style={{ transitionProperty: "color" }}
            >
              {mode === "login" ? "Create one →" : "Sign in →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
