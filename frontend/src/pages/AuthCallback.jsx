import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { http } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      navigate("/login", { replace: true });
      return;
    }
    const session_id = decodeURIComponent(match[1]);

    (async () => {
      try {
        const { data } = await http.post(
          "/auth/google/session",
          { session_id },
          { headers: { "X-Session-ID": session_id } }
        );
        setUser(data);
        window.history.replaceState(null, "", "/");
        navigate("/", { replace: true });
      } catch (e) {
        navigate("/login", { replace: true, state: { error: "Google login failed." } });
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#050505] text-white">
      <div className="font-mono text-sm text-neutral-400" data-testid="auth-callback-processing">
        Establishing secure session…
      </div>
    </div>
  );
}
