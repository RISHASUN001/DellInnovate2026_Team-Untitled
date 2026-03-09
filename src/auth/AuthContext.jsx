import { createContext, useContext, useState, useEffect } from "react";
import { mockLogin, mockGetCurrentUser, mockLogout } from "./mockAuth.js";

const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8010";
const AUTH_SERVICE_URL = import.meta.env.VITE_AUTH_SERVICE_URL || "http://localhost:8001";

// ─── Auth Context ─────────────────────────────────────────────────────────────
// AUTH_SERVICE_CALL: All functions in this file delegate to mockAuth.js.
// When integrating a real auth service, swap the mockAuth imports and replace
// the logic inside `login`, `logout`, and the boot effect to call your API.

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);   // true while validating persisted session
  const [authError, setAuthError] = useState("");

  const normalizeGoogleUser = (userinfo = {}) => {
    const email = userinfo.email || "";
    // Assign role based on email
    let role = "admin";
    if (email === "lisa12072004l@gmail.com") {
      role = "Youth Helper";
    }
    
    return {
      id: userinfo.sub || userinfo.email || "google-user",
      name: userinfo.name || userinfo.email || "Google User",
      email: email,
      role: role,
      provider: "google",
      picture: userinfo.picture,
    };
  };

  const exchangeGoogleCode = async (code) => {
    const resp = await fetch(`${API_GATEWAY_URL}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });

    if (!resp.ok) {
      const error = await resp.json().catch(() => ({}));
      throw new Error(error.detail || error.error || "Google token exchange failed.");
    }

    const data = await resp.json();
    const accessToken = data?.tokens?.access_token;
    if (!accessToken) {
      throw new Error("OAuth exchange succeeded but access token is missing.");
    }

    const normalizedUser = normalizeGoogleUser(data?.userinfo || {});
    sessionStorage.setItem("scs_auth_token", accessToken);
    sessionStorage.setItem("scs_auth_user", JSON.stringify(normalizedUser));
    setUser(normalizedUser);
  };

  // ── On mount: restore session from storage ──────────────────────────────────
  // AUTH_SERVICE_CALL: replace with a GET /api/auth/me call using stored token.
  useEffect(() => {
    const init = async () => {
      try {
        const params = new URLSearchParams(window.location.search);
        const oauthCode = params.get("code");

        if (oauthCode) {
          const handledCodeKey = `scs_oauth_code_handled_${oauthCode}`;
          const alreadyHandled = sessionStorage.getItem(handledCodeKey) === "1";

          params.delete("code");
          const cleaned = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
          window.history.replaceState({}, document.title, cleaned);

          if (alreadyHandled) {
            return;
          }

          sessionStorage.setItem(handledCodeKey, "1");
          await exchangeGoogleCode(oauthCode);
          params.delete("code");
          return;
        }

        const token = sessionStorage.getItem("scs_auth_token");
        if (!token) return;

        const savedUser = sessionStorage.getItem("scs_auth_user");
        if (savedUser) {
          try {
            setUser(JSON.parse(savedUser));
          } catch {
            sessionStorage.removeItem("scs_auth_user");
          }
        }

        const authHeader = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
        const verifyResp = await fetch(`${AUTH_SERVICE_URL}/me`, {
          method: "GET",
          headers: { Authorization: authHeader },
        });

        if (!verifyResp.ok) {
          sessionStorage.removeItem("scs_auth_token");
          sessionStorage.removeItem("scs_auth_user");
          setUser(null);
        }
      } catch (error) {
        if (error?.message) {
          setAuthError(error.message);
        }
        sessionStorage.removeItem("scs_auth_token");
        sessionStorage.removeItem("scs_auth_user");
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    init();
  }, []);

  // ── Login ───────────────────────────────────────────────────────────────────
  const login = async (email, password) => {
    setAuthError("");
    // AUTH_SERVICE_CALL: mockLogin → POST /api/auth/login
    const { user: u, token } = await mockLogin(email, password);
    sessionStorage.setItem("scs_auth_token", token);
    sessionStorage.setItem("scs_auth_user", JSON.stringify(u));
    setUser(u);
  };

  const loginWithGoogle = () => {
    setAuthError("");
    const frontendRedirect = encodeURIComponent(window.location.origin);
    window.location.href = `${API_GATEWAY_URL}/login?frontend_redirect=${frontendRedirect}`;
  };

  // ── Logout ──────────────────────────────────────────────────────────────────
  const logout = async () => {
    // AUTH_SERVICE_CALL: mockLogout → POST /api/auth/logout
    await mockLogout();
    sessionStorage.removeItem("scs_auth_token");
    sessionStorage.removeItem("scs_auth_user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, authError, setAuthError, login, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// Convenience hook — throws if used outside provider
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be called within <AuthProvider>.");
  return ctx;
}
