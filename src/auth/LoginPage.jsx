import { useState } from "react";
import { useAuth } from "./AuthContext.jsx";
import { DEMO_CREDENTIALS } from "./mockAuth.js";
import { Icon } from "../components/Icons.jsx";

// ─── Design tokens (mirrors the main app) ─────────────────────────────────────
const T = {
  navy: "#0f172a",
  navyMid: "#1e293b",
  slate: "#475569",
  muted: "#94a3b8",
  border: "#e2e8f0",
  bg: "#f0f4f8",
  indigo: "#0672CB",
  indigoDark: "#0460a9",
  violet: "#0460a9",
  success: "#10b981",
  danger: "#dc2626",
};

const ROLE_BADGE = {
  Admin: { bg: "#ede9fe", text: "#5b21b6" },
  "Youth Helper": { bg: "#dbeafe", text: "#1e40af" },
};

export default function LoginPage() {
  const { login, authError, setAuthError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fieldErr, setFieldErr] = useState({});

  const validate = () => {
    const errs = {};
    if (!email.trim()) errs.email = "Email is required.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      errs.email = "Enter a valid email address.";
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
    <div
      style={{
        minHeight: "100vh",
        backgroundImage: "url('/image.png')",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundAttachment: "fixed",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Segoe UI', system-ui, sans-serif",
        padding: "24px 16px",
      }}
    >
      <div style={{ width: "100%", maxWidth: 420 }}>
        {/* ── Branding ── */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 52,
              height: 52,
              borderRadius: 14,
              background: "linear-gradient(135deg, #0672CB, #0460a9)",
              marginBottom: 14,
              boxShadow: "0 6px 20px rgba(6,114,203,0.3)",
            }}
          >
            <Icon.Shield size={26} color="#fff" />
          </div>
          <div
            style={{
              color: "#1e293b",
              fontWeight: 700,
              fontSize: 18,
              letterSpacing: "0.2px",
            }}
          >
            Singapore Children's Society
          </div>
          <div
            style={{
              color: "#64748b",
              fontSize: 11,
              letterSpacing: "1.5px",
              textTransform: "uppercase",
              marginTop: 3,
            }}
          >
            YOUTH<sup>TH</sup>CARE - Case Management
          </div>
        </div>

        {/* ── Login card ── */}
        <div
          style={{
            background: "rgba(255,255,255,0.95)",
            backdropFilter: "blur(12px)",
            borderRadius: 14,
            padding: "28px 28px 24px",
            boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
            border: "1px solid rgba(6,114,203,0.1)",
          }}
        >
          <h2
            style={{
              margin: "0 0 4px",
              fontSize: 17,
              fontWeight: 700,
              color: T.navyMid,
            }}
          >
            Sign in to your account
          </h2>
          <p style={{ margin: "0 0 20px", fontSize: 12, color: T.muted }}>
            Use your @scs.org.sg credentials to access the dashboard.
          </p>

          {/* Global auth error */}
          {authError && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 8,
                padding: "10px 12px",
                marginBottom: 16,
              }}
            >
              <Icon.AlertCircle size={15} color={T.danger} />
              <span style={{ fontSize: 13, color: "#991b1b" }}>
                {authError}
              </span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            {/* Email */}
            <div style={{ marginBottom: 16 }}>
              <label
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: T.navyMid,
                  display: "block",
                  marginBottom: 5,
                  letterSpacing: "0.3px",
                }}
              >
                Work Email
              </label>
              <input
                type="email"
                value={email}
                autoComplete="username"
                onChange={(e) => {
                  setEmail(e.target.value);
                  setFieldErr((p) => ({ ...p, email: "" }));
                }}
                placeholder="you@scs.org.sg"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: "10px 12px",
                  borderRadius: 9,
                  fontSize: 13,
                  border: `1.5px solid ${fieldErr.email ? T.danger : T.border}`,
                  outline: "none",
                  fontFamily: "inherit",
                  background: "#fafafa",
                  transition: "border-color 0.15s",
                }}
                onFocus={(e) => (e.target.style.borderColor = T.indigo)}
                onBlur={(e) =>
                  (e.target.style.borderColor = fieldErr.email
                    ? T.danger
                    : T.border)
                }
              />
              {fieldErr.email && (
                <div style={{ fontSize: 11, color: T.danger, marginTop: 4 }}>
                  {fieldErr.email}
                </div>
              )}
            </div>

            {/* Password */}
            <div style={{ marginBottom: 24 }}>
              <label
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: T.navyMid,
                  display: "block",
                  marginBottom: 5,
                  letterSpacing: "0.3px",
                }}
              >
                Password
              </label>
              <div style={{ position: "relative" }}>
                <input
                  type={showPw ? "text" : "password"}
                  value={password}
                  autoComplete="current-password"
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setFieldErr((p) => ({ ...p, password: "" }));
                  }}
                  placeholder="Enter your password"
                  style={{
                    width: "100%",
                    boxSizing: "border-box",
                    padding: "10px 40px 10px 12px",
                    borderRadius: 9,
                    fontSize: 13,
                    border: `1.5px solid ${fieldErr.password ? T.danger : T.border}`,
                    outline: "none",
                    fontFamily: "inherit",
                    background: "#fafafa",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = T.indigo)}
                  onBlur={(e) =>
                    (e.target.style.borderColor = fieldErr.password
                      ? T.danger
                      : T.border)
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowPw((p) => !p)}
                  style={{
                    position: "absolute",
                    right: 10,
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: T.muted,
                    padding: 2,
                    display: "flex",
                    alignItems: "center",
                  }}
                >
                  <Icon.Eye size={15} />
                </button>
              </div>
              {fieldErr.password && (
                <div style={{ fontSize: 11, color: T.danger, marginTop: 4 }}>
                  {fieldErr.password}
                </div>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "11px",
                background: loading
                  ? "#a5b4fc"
                  : `linear-gradient(135deg, ${T.indigo}, ${T.violet})`,
                color: "#fff",
                border: "none",
                borderRadius: 9,
                fontWeight: 700,
                fontSize: 14,
                cursor: loading ? "wait" : "pointer",
                boxShadow: loading
                  ? "none"
                  : "0 4px 14px rgba(99,102,241,0.35)",
                transition: "all 0.2s",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
              }}
            >
              {loading ? (
                <>
                  <div
                    style={{
                      width: 16,
                      height: 16,
                      border: "2px solid rgba(255,255,255,0.3)",
                      borderTopColor: "#fff",
                      borderRadius: "50%",
                      animation: "spin 0.7s linear infinite",
                    }}
                  />
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
        <div
          style={{
            marginTop: 18,
            background: "rgba(255,255,255,0.85)",
            backdropFilter: "blur(8px)",
            border: "1px solid rgba(6,114,203,0.12)",
            borderRadius: 10,
            padding: "14px 16px",
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#64748b",
              textTransform: "uppercase",
              letterSpacing: "0.8px",
              marginBottom: 10,
            }}
          >
            Demo Credentials - click to fill
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {DEMO_CREDENTIALS.map((c, i) => {
              const badge = ROLE_BADGE[c.role];
              return (
                <button
                  key={i}
                  onClick={() => fillCreds(c)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    background: "#f8fafc",
                    border: "1px solid #e2e8f0",
                    borderRadius: 8,
                    padding: "8px 12px",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "#f0f7ff";
                    e.currentTarget.style.borderColor = "#0672CB";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "#f8fafc";
                    e.currentTarget.style.borderColor = "#e2e8f0";
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontWeight: 600,
                        fontSize: 12,
                        color: "#1e293b",
                      }}
                    >
                      {c.name}
                    </div>
                    <div
                      style={{ fontSize: 10, color: "#64748b", marginTop: 1 }}
                    >
                      {c.email}
                    </div>
                  </div>
                  <span
                    style={{
                      background: badge.bg,
                      color: badge.text,
                      borderRadius: 16,
                      padding: "3px 10px",
                      fontSize: 10,
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                      marginLeft: 12,
                    }}
                  >
                    {c.role}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Privacy note ── */}
        <div
          style={{
            textAlign: "center",
            marginTop: 14,
            fontSize: 10,
            color: "#64748b",
            lineHeight: 1.5,
          }}
        >
          <Icon.Lock
            size={10}
            color="#64748b"
            style={{
              display: "inline",
              verticalAlign: "middle",
              marginRight: 4,
            }}
          />
          Secured by SCS Identity Platform - Data protected under PDPA
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        * { -webkit-font-smoothing: antialiased; }
      `}</style>
    </div>
  );
}
