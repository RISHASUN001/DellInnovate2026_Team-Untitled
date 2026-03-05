import { useState } from "react";
import { useAuth } from "./AuthContext.jsx";
import { DEMO_CREDENTIALS } from "./mockAuth.js";
import { Icon } from "../components/Icons.jsx";

// ─── Design tokens (mirrors the main app) ─────────────────────────────────────
const T = {
  navy:    "#0f172a",
  navyMid: "#1e293b",
  slate:   "#475569",
  muted:   "#94a3b8",
  border:  "#e2e8f0",
  bg:      "#f0f4f8",
  indigo:  "#6366f1",
  indigoDark: "#4338ca",
  violet:  "#8b5cf6",
  success: "#10b981",
  danger:  "#dc2626",
};

const ROLE_BADGE = {
  Admin:         { bg: "#ede9fe", text: "#5b21b6" },
  "Youth Helper":{ bg: "#dbeafe", text: "#1e40af" },
};

export default function LoginPage() {
  const { login, authError, setAuthError } = useAuth();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw]     = useState(false);
  const [loading, setLoading]   = useState(false);
  const [fieldErr, setFieldErr] = useState({});

  const validate = () => {
    const errs = {};
    if (!email.trim()) errs.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = "Enter a valid email address.";
    if (!password) errs.password = "Password is required.";
    setFieldErr(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");
    if (!validate()) return;
    setLoading(true);
    try {
      await login(email, password);
      // AuthContext sets the user — App will re-render into the dashboard
    } catch (err) {
      setAuthError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fillCreds = (cred) => {
    setEmail(cred.email);
    setPassword(cred.password);
    setFieldErr({});
    setAuthError("");
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: `linear-gradient(135deg, ${T.navy} 0%, #1a2744 60%, #1e293b 100%)`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      padding: "24px 16px",
    }}>
      <div style={{ width: "100%", maxWidth: 440 }}>

        {/* ── Branding ── */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 56, height: 56, borderRadius: 16,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            marginBottom: 16, boxShadow: "0 8px 24px rgba(99,102,241,0.4)",
          }}>
            <Icon.Shield size={28} color="#fff" />
          </div>
          <div style={{ color: "#fff", fontWeight: 700, fontSize: 20, letterSpacing: "0.2px" }}>
            Singapore Children's Society
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12, letterSpacing: "2px", textTransform: "uppercase", marginTop: 3 }}>
            YOUTH<sup>TH</sup>CARE · Case Management
          </div>
        </div>

        {/* ── Login card ── */}
        <div style={{
          background: "#fff",
          borderRadius: 16,
          padding: "32px 32px 28px",
          boxShadow: "0 24px 60px rgba(0,0,0,0.4)",
          border: "1px solid rgba(255,255,255,0.08)",
        }}>
          <h2 style={{ margin: "0 0 6px", fontSize: 18, fontWeight: 700, color: T.navyMid }}>
            Sign in to your account
          </h2>
          <p style={{ margin: "0 0 24px", fontSize: 13, color: T.muted }}>
            Use your @scs.org.sg credentials to access the dashboard.
          </p>

          {/* Global auth error */}
          {authError && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              background: "#fef2f2", border: "1px solid #fecaca",
              borderRadius: 8, padding: "10px 12px", marginBottom: 16,
            }}>
              <Icon.AlertCircle size={15} color={T.danger} />
              <span style={{ fontSize: 13, color: "#991b1b" }}>{authError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            {/* Email */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: T.navyMid, display: "block", marginBottom: 5, letterSpacing: "0.3px" }}>
                Work Email
              </label>
              <input
                type="email"
                value={email}
                autoComplete="username"
                onChange={e => { setEmail(e.target.value); setFieldErr(p => ({ ...p, email: "" })); }}
                placeholder="you@scs.org.sg"
                style={{
                  width: "100%", boxSizing: "border-box",
                  padding: "10px 12px", borderRadius: 9, fontSize: 13,
                  border: `1.5px solid ${fieldErr.email ? T.danger : T.border}`,
                  outline: "none", fontFamily: "inherit",
                  background: "#fafafa",
                  transition: "border-color 0.15s",
                }}
                onFocus={e => e.target.style.borderColor = T.indigo}
                onBlur={e => e.target.style.borderColor = fieldErr.email ? T.danger : T.border}
              />
              {fieldErr.email && <div style={{ fontSize: 11, color: T.danger, marginTop: 4 }}>{fieldErr.email}</div>}
            </div>

            {/* Password */}
            <div style={{ marginBottom: 24 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: T.navyMid, display: "block", marginBottom: 5, letterSpacing: "0.3px" }}>
                Password
              </label>
              <div style={{ position: "relative" }}>
                <input
                  type={showPw ? "text" : "password"}
                  value={password}
                  autoComplete="current-password"
                  onChange={e => { setPassword(e.target.value); setFieldErr(p => ({ ...p, password: "" })); }}
                  placeholder="Enter your password"
                  style={{
                    width: "100%", boxSizing: "border-box",
                    padding: "10px 40px 10px 12px", borderRadius: 9, fontSize: 13,
                    border: `1.5px solid ${fieldErr.password ? T.danger : T.border}`,
                    outline: "none", fontFamily: "inherit",
                    background: "#fafafa",
                  }}
                  onFocus={e => e.target.style.borderColor = T.indigo}
                  onBlur={e => e.target.style.borderColor = fieldErr.password ? T.danger : T.border}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(p => !p)}
                  style={{
                    position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                    background: "none", border: "none", cursor: "pointer", color: T.muted, padding: 2,
                    display: "flex", alignItems: "center",
                  }}
                >
                  <Icon.Eye size={15} />
                </button>
              </div>
              {fieldErr.password && <div style={{ fontSize: 11, color: T.danger, marginTop: 4 }}>{fieldErr.password}</div>}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%", padding: "11px",
                background: loading ? "#a5b4fc" : `linear-gradient(135deg, ${T.indigo}, ${T.violet})`,
                color: "#fff", border: "none", borderRadius: 9,
                fontWeight: 700, fontSize: 14, cursor: loading ? "wait" : "pointer",
                boxShadow: loading ? "none" : "0 4px 14px rgba(99,102,241,0.35)",
                transition: "all 0.2s",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              }}
            >
              {loading ? (
                <>
                  <div style={{
                    width: 16, height: 16, border: "2px solid rgba(255,255,255,0.3)",
                    borderTopColor: "#fff", borderRadius: "50%",
                    animation: "spin 0.7s linear infinite",
                  }} />
                  Signing in…
                </>
              ) : (
                <>
                  <Icon.Lock size={15} color="#fff" />
                  Sign In
                </>
              )}
            </button>
          </form>
        </div>

        {/* ── Demo credentials table ── */}
        <div style={{
          marginTop: 20,
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 12,
          padding: "16px 18px",
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 10 }}>
            Demo Credentials — click to fill
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {DEMO_CREDENTIALS.map((c, i) => {
              const badge = ROLE_BADGE[c.role];
              return (
                <button
                  key={i}
                  onClick={() => fillCreds(c)}
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 8, padding: "8px 12px", cursor: "pointer", textAlign: "left",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.13)"}
                  onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.07)"}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12, color: "#f1f5f9" }}>{c.name}</div>
                    <div style={{ fontSize: 11, color: "#64748b", marginTop: 1 }}>{c.email} · {c.password}</div>
                  </div>
                  <span style={{
                    background: badge.bg, color: badge.text,
                    borderRadius: 20, padding: "2px 9px", fontSize: 10, fontWeight: 700, whiteSpace: "nowrap", marginLeft: 12,
                  }}>
                    {c.role}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Privacy note ── */}
        <div style={{ textAlign: "center", marginTop: 16, fontSize: 11, color: "#4b5563", lineHeight: 1.5 }}>
          <Icon.Lock size={11} color="#4b5563" style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
          Secured by SCS Identity Platform · Data protected under PDPA
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        * { -webkit-font-smoothing: antialiased; }
      `}</style>
    </div>
  );
}
