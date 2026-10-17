import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "@/App.css";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import Login from "@/pages/Login";
import AuthCallback from "@/pages/AuthCallback";
import Chat from "@/pages/Chat";
import Connections from "@/pages/Connections";
import Dashboard from "@/pages/Dashboard";
import { Toaster } from "sonner";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#050505] text-white">
        <div className="font-mono text-xs text-neutral-500 tracking-widest">AUTHENTICATING…</div>
      </div>
    );
  }
  if (user === false) return <Navigate to="/login" replace />;
  return children;
}

function Router() {
  const location = useLocation();
  // Handle Emergent OAuth callback (session_id in URL fragment) synchronously
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Chat /></Protected>} />
      <Route path="/chat/:chatId" element={<Protected><Chat /></Protected>} />
      <Route path="/connections" element={<Protected><Connections /></Protected>} />
      <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Router />
        <Toaster theme="dark" position="bottom-right" />
      </BrowserRouter>
    </AuthProvider>
  );
}
