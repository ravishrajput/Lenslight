import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { X, Loader2, Mail, Check } from "lucide-react";

export default function DigestSettings({ open, onClose }) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [digestEmail, setDigestEmail] = useState("");
  const [accountEmail, setAccountEmail] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setStatus("");
    setError("");
    setLoading(true);
    http.get("/digests/me")
      .then(({ data }) => {
        setSubscribed(!!data.subscribed);
        setDigestEmail(data.digest_email || data.email || "");
        setAccountEmail(data.email || "");
      })
      .catch((e) => setError(formatApiError(e.response?.data?.detail) || e.message))
      .finally(() => setLoading(false));
  }, [open]);

  const save = async (nextSubscribed) => {
    setSaving(true);
    setError("");
    try {
      const { data } = await http.post("/digests/subscribe", {
        subscribed: nextSubscribed,
        digest_email: digestEmail || null,
      });
      setSubscribed(!!data.subscribed);
      setDigestEmail(data.digest_email || digestEmail);
      setStatus(nextSubscribed ? "Subscribed — you'll get a digest every Monday 09:00 UTC." : "Unsubscribed.");
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setSaving(false);
    }
  };

  const sendPreview = async () => {
    setSending(true);
    setStatus("");
    setError("");
    try {
      // Save current digest email first so the preview goes there
      await http.post("/digests/subscribe", { subscribed, digest_email: digestEmail || null });
      const { data } = await http.post("/digests/preview", {});
      setStatus(`Queued — a preview digest is being generated and sent to ${data.email}. It may take ~30-60 seconds.`);
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setSending(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      data-testid="digest-settings-modal"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-[#0a0a0a] border border-white/15 snap-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div>
            <div className="font-mono text-[10px] tracking-[0.3em] text-neutral-500 mb-1">// WEEKLY DIGEST</div>
            <h2 className="font-display text-xl font-bold text-white">Monday morning briefing</h2>
          </div>
          <button
            data-testid="close-digest-settings"
            onClick={onClose}
            className="p-1.5 text-neutral-500 hover:text-white"
            style={{ transitionProperty: "color" }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-5 space-y-5">
          <p className="text-sm text-neutral-400 leading-relaxed">
            Every Monday at <span className="font-mono text-neutral-200">09:00 UTC</span>, we'll analyze last week's
            checkout, cart, and revenue anomalies with Claude and email you a one-page digest.
          </p>

          {loading ? (
            <div className="flex items-center gap-2 font-mono text-xs text-neutral-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading preferences…
            </div>
          ) : (
            <>
              <div>
                <label className="font-mono text-[10px] tracking-widest text-neutral-500 uppercase block mb-2">
                  Deliver to
                </label>
                <div className="flex items-center gap-2 border border-white/15 bg-[#050505] focus-within:border-white/40"
                     style={{ transitionProperty: "border-color" }}>
                  <Mail className="w-3.5 h-3.5 text-neutral-500 ml-3" />
                  <input
                    type="email"
                    value={digestEmail}
                    onChange={(e) => setDigestEmail(e.target.value)}
                    placeholder="you@company.com"
                    data-testid="digest-email-input"
                    className="flex-1 bg-transparent px-2 py-2.5 text-sm text-white font-mono focus:outline-none"
                  />
                </div>
                <div className="font-mono text-[10px] text-neutral-600 mt-1.5">
                  Account email: {accountEmail}. You can route digests to a different inbox.
                </div>
              </div>

              <div className="flex items-center justify-between border border-white/10 bg-[#050505] px-4 py-3">
                <div>
                  <div className="text-sm text-white font-medium">Weekly digest</div>
                  <div className="font-mono text-[10px] text-neutral-500 mt-0.5">
                    {subscribed ? "ACTIVE — next send Monday 09:00 UTC" : "OFF — no scheduled sends"}
                  </div>
                </div>
                <button
                  onClick={() => save(!subscribed)}
                  disabled={saving}
                  data-testid="digest-subscribe-toggle"
                  className={`relative w-12 h-6 border ${subscribed ? "bg-[#F24E1E] border-[#F24E1E]" : "bg-transparent border-white/30"} disabled:opacity-50`}
                  style={{ transitionProperty: "background-color, border-color" }}
                >
                  <span
                    className={`absolute top-0.5 w-4 h-4 bg-white ${subscribed ? "right-1" : "left-1"}`}
                    style={{ transitionProperty: "left, right" }}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={sendPreview}
                  disabled={sending || !digestEmail}
                  data-testid="digest-send-preview-btn"
                  className="inline-flex items-center gap-2 border border-white/20 px-4 py-2 text-xs font-mono tracking-widest uppercase text-white hover:border-white/60 disabled:opacity-50"
                  style={{ transitionProperty: "border-color" }}
                >
                  {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
                  Send preview now
                </button>
              </div>

              {status && (
                <div
                  data-testid="digest-status"
                  className="flex items-start gap-2 font-mono text-xs text-[#00E676] border border-[#00E676]/30 bg-[#00E676]/5 px-3 py-2"
                >
                  <Check className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  <span>{status}</span>
                </div>
              )}
              {error && (
                <div
                  data-testid="digest-error"
                  className="font-mono text-xs text-[#E63946] border border-[#E63946]/40 bg-[#E63946]/5 px-3 py-2"
                >
                  {error}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
