import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import { AuthProvider, useAuth } from './auth/AuthContext.jsx'
import LoginPage from './auth/LoginPage.jsx'
import AdminDashboard from './admin/AdminDashboard.jsx'
import YouthHelperDashboard from './scs_dashboard.jsx'
import EnhancedDashboard from './components/EnhancedDashboard.jsx'

// ─── Role-based router ────────────────────────────────────────────────────────
// Renders the correct dashboard based on authenticated user role.
// Replace this component with a proper router (React Router, TanStack Router, etc.)
// once real auth is integrated.
function AppRouter() {
  const { user, loading } = useAuth();
  const [useEnhanced, setUseEnhanced] = useState(true); // Toggle for new dashboard

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "#f0f4f8",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Segoe UI', system-ui, sans-serif",
      }}>
        <div style={{ textAlign: "center", color: "#475569" }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            border: "3px solid #0672CB",
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

  // Use Enhanced Dashboard for all users (unified experience)
  // Toggle between enhanced and legacy dashboards if needed
  if (useEnhanced) {
    return <EnhancedDashboard currentUser={user} />;
  }

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

