import React from 'react'
import ReactDOM from 'react-dom/client'
import { AuthProvider, useAuth } from './auth/AuthContext.jsx'
import LoginPage from './auth/LoginPage.jsx'
import AdminDashboard from './admin/AdminDashboard.jsx'
import YouthHelperDashboard from './scs_dashboard.jsx'

// ─── Role-based router ────────────────────────────────────────────────────────
// Renders the correct dashboard based on authenticated user role.
// Replace this component with a proper router (React Router, TanStack Router, etc.)
// once real auth is integrated.
function AppRouter() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "#0f172a",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Segoe UI', system-ui, sans-serif",
      }}>
        <div style={{ textAlign: "center", color: "#94a3b8" }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            border: "3px solid #6366f1",
            borderTopColor: "transparent",
            animation: "spin 0.7s linear infinite",
            margin: "0 auto 12px",
          }} />
          <div style={{ fontSize: 13 }}>Loading session…</div>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  // AUTH_SERVICE_CALL: role comes from the authenticated user object returned by
  // your auth service. MongoDB roles are lowercase: "admin" or "youth_helper"
  // Admin-only access to AdminDashboard; helpers go to YouthHelperDashboard
  if (user.role === "admin") return <AdminDashboard currentUser={user} />;
  return <YouthHelperDashboard currentUser={user} />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  </React.StrictMode>,
)

