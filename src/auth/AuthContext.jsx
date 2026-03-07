import { createContext, useContext, useState, useEffect } from "react";
import { mockLogin, mockGetCurrentUser, mockLogout } from "./mockAuth.js";

// ─── Auth Context ─────────────────────────────────────────────────────────────
// AUTH_SERVICE_CALL: All functions in this file delegate to mockAuth.js.
// When integrating a real auth service, swap the mockAuth imports and replace
// the logic inside `login`, `logout`, and the boot effect to call your API.

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);   // true while validating persisted session
  const [authError, setAuthError] = useState("");

  // ── On mount: restore session from storage ──────────────────────────────────
  // AUTH_SERVICE_CALL: replace with a GET /api/auth/me call using stored token.
  useEffect(() => {
    const token = sessionStorage.getItem("scs_auth_token");
    if (!token) {
      setLoading(false);
      return;
    }
    mockGetCurrentUser(token)
      .then(u => setUser(u))
      .catch(() => sessionStorage.removeItem("scs_auth_token"))
      .finally(() => setLoading(false));
  }, []);

  // ── Login ───────────────────────────────────────────────────────────────────
  const login = async (email, password) => {
    setAuthError("");
    // AUTH_SERVICE_CALL: mockLogin → POST /api/auth/login
    const { user: u, token } = await mockLogin(email, password);
    sessionStorage.setItem("scs_auth_token", token);
    setUser(u);
  };

  // ── Logout ──────────────────────────────────────────────────────────────────
  const logout = async () => {
    // AUTH_SERVICE_CALL: mockLogout → POST /api/auth/logout
    await mockLogout();
    sessionStorage.removeItem("scs_auth_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, authError, setAuthError, login, logout }}>
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
