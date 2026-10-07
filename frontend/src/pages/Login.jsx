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

  const googleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-5 bg-[#050505] text-white grain">
      {/* Left: visual */}
      <div className="hidden lg:block lg:col-span-3 relative overflow-hidden border-r border-white/10">
        <img src={AUTH_BG} alt="" className="absolute inset-0 w-full h-full object-cover opacity-60" />
        <div className="absolute inset-0 bg-gradient-to-tr from-black/80 via-black/30 to-black/70" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12">
          <div className="flex items-center gap-2 font-mono text-xs tracking-widest text-neutral-300" data-testid="brand-logo">
            <span className="inline-block w-2 h-2 bg-[#F24E1E]" />
            <span>INSIGHTLENS / v0.1</span>
          </div>
          <div className="max-w-xl">
            <div className="font-mono text-xs tracking-[0.3em] text-neutral-400 mb-4">INTELLIGENCE / SPLUNK · BIGQUERY</div>
            <h1 className="font-display text-5xl lg:text-6xl font-black leading-[0.95] mb-6">
              Ask your data.<br />
              <span className="text-neutral-500">Get a report back.</span>
            </h1>
            <p className="text-neutral-300 text-base max-w-md">
              A ChatGPT-style terminal wired directly into your observability and warehouse stack. Prompt it. It writes the SQL and SPL for you.
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
            onClick={googleLogin}
            data-testid="google-login-btn"
            className="w-full mb-5 flex items-center justify-center gap-3 border border-white/20 py-3 text-sm hover:border-white/50 hover:bg-white/[0.03]"
            style={{ transitionProperty: "background-color, border-color" }}
          >
            <svg width="16" height="16" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.4H42V20H24v8h11.3C33.9 32.4 29.4 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 5 29.3 3 24 3 12.3 3 3 12.3 3 24s9.3 21 21 21 21-9.3 21-21c0-1.2-.1-2.3-.4-3.6z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34 5 29.3 3 24 3 15.9 3 8.9 7.6 6.3 14.7z"/><path fill="#4CAF50" d="M24 45c5.1 0 9.8-2 13.3-5.1l-6.1-5.2C29.1 36.3 26.7 37 24 37c-5.3 0-9.8-3.5-11.4-8.4l-6.6 5.1C8.4 40.3 15.6 45 24 45z"/><path fill="#1976D2" d="M43.6 20.4H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.2 5.6l6.1 5.2c-.4.4 6.6-4.8 6.6-14.8 0-1.2-.1-2.3-.4-3.6z"/></svg>
            <span>Continue with Google</span>
          </button>

          <div className="flex items-center gap-3 mb-5">
            <div className="h-px bg-white/10 flex-1" />
            <span className="font-mono text-[10px] text-neutral-500 tracking-widest">OR WITH EMAIL</span>
            <div className="h-px bg-white/10 flex-1" />
          </div>

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
