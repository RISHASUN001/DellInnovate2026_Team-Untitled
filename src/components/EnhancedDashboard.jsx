import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
} from "recharts";
import { useAuth } from "../auth/AuthContext.jsx";
import { Icon } from "./Icons.jsx";
import { caseAPI, historyAPI } from "../services/api.js";

// ─── SERVICE URLS ────────────────────────────────────────────────────────────
const CASE_SERVICE_URL = "http://localhost:8003";
const CHATBOT_SERVICE_URL = "http://localhost:8000";

// ─── DESIGN TOKENS ───────────────────────────────────────────────────────────
const T = {
  navy: "#0f172a",
  navyMid: "#1e293b",
  slate: "#475569",
  muted: "#94a3b8",
  border: "#e2e8f0",
  bg: "#f0f4f8",
  cardBg: "#ffffff",
  indigo: "#0672CB",
  indigoDark: "#0460a9",
  success: "#10b981",
  danger: "#dc2626",
  warning: "#f59e0b",
};

// ─── RISK COLOR MAPPINGS ─────────────────────────────────────────────────────
const RISK_COLORS = {
  1: { bg: "#d1fae5", text: "#065f46", label: "Low" },
  2: { bg: "#dbeafe", text: "#1e40af", label: "Low-Med" },
  3: { bg: "#fef3c7", text: "#92400e", label: "Medium" },
  4: { bg: "#ffedd5", text: "#c2410c", label: "High" },
  5: { bg: "#fee2e2", text: "#991b1b", label: "Critical" },
};

const riskColors = {
  CRITICAL: { bg: "#fef2f2", text: "#991b1b", border: "#fecaca", dot: "#dc2626" },
  HIGH: { bg: "#fff7ed", text: "#c2410c", border: "#fed7aa", dot: "#ea580c" },
  MEDIUM: { bg: "#fefce8", text: "#a16207", border: "#fef08a", dot: "#ca8a04" },
  LOW: { bg: "#f0fdf4", text: "#166534", border: "#bbf7d0", dot: "#16a34a" },
};

const riskLevelToLabel = (level) => {
  if (level >= 5) return "CRITICAL";
  if (level >= 4) return "HIGH";
  if (level >= 3) return "MEDIUM";
  return "LOW";
};

const CHART_COLORS = {
  critical: "#dc2626",
  high: "#ea580c",
  moderate: "#ca8a04",
  low: "#16a34a",
  primary: "#0672CB",
};

// ─── DATA FRESHNESS INDICATOR ────────────────────────────────────────────────
function DataFreshnessIndicator() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        background: "rgba(255,255,255,0.08)",
        border: "1px solid rgba(255,255,255,0.15)",
        borderRadius: 10,
        padding: "8px 14px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Icon.RefreshCw size={14} color="#cbd5e1" />
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#cbd5e1", letterSpacing: "0.5px" }}>
            LAST INGESTION
          </div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>
            Today, 06:12 AM · Next in ~3h 48m
          </div>
        </div>
      </div>
      <div style={{ width: 1, height: 30, background: "rgba(255,255,255,0.2)", margin: "0 4px" }} />
      <div style={{ fontSize: 10, color: "#94a3b8", maxWidth: 140, lineHeight: 1.35 }}>
        Data refreshes every <strong>6 hours</strong> for privacy & platform compliance.
      </div>
    </div>
  );
}

// ─── RISK BADGE ──────────────────────────────────────────────────────────────
function RiskBadge({ level, score }) {
  const cfg = RISK_COLORS[level] || RISK_COLORS[3];
  return (
    <span
      style={{
        background: cfg.bg,
        color: cfg.text,
        padding: "3px 10px",
        borderRadius: 8,
        fontSize: 11,
        fontWeight: 700,
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      {cfg.label}
      {score && <span style={{ fontWeight: 500 }}>({score.toFixed(1)}%)</span>}
    </span>
  );
}

// ─── WORK STATUS BADGE ───────────────────────────────────────────────────────
function WorkStatusBadge({ workStatus }) {
  const cfg = {
    not_started: { bg: "#f3f4f6", text: "#4b5563", label: "Not Started" },
    in_progress: { bg: "#dbeafe", text: "#1e40af", label: "In Progress" },
    to_review: { bg: "#fee2e2", text: "#991b1b", label: "To Review" },
    completed: { bg: "#d1fae5", text: "#065f46", label: "Completed" },
  };
  const c = cfg[workStatus] || { bg: "#f3f4f6", text: "#4b5563", label: workStatus || "—" };
  return (
    <span
      style={{
        background: c.bg,
        color: c.text,
        padding: "2px 9px",
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {c.label}
    </span>
  );
}

// ─── CASE PANEL CARD (grid display) ──────────────────────────────────────────
function CasePanelCard({ c, onClick, isSelected }) {
  const rc = riskColors[c.risk] || riskColors.MEDIUM;
  return (
    <div
      onClick={() => onClick(c)}
      style={{
        background: isSelected ? "#eff6ff" : "#fff",
        border: isSelected ? `2px solid ${T.indigo}` : "1px solid #e2e8f0",
        borderRadius: 14,
        padding: "18px 20px",
        cursor: "pointer",
        transition: "all 0.2s",
        boxShadow: isSelected ? "0 6px 20px rgba(6,114,203,0.2)" : "0 2px 8px rgba(0,0,0,0.04)",
        display: "flex",
        flexDirection: "column",
        gap: 12,
        minHeight: 140,
      }}
      onMouseEnter={(e) => {
        if (!isSelected) e.currentTarget.style.boxShadow = "0 4px 14px rgba(0,0,0,0.08)";
      }}
      onMouseLeave={(e) => {
        if (!isSelected) e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.04)";
      }}
    >
      {/* Header Row */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: T.navyMid }}>{c.id}</div>
          <div style={{ fontSize: 13, color: T.slate, marginTop: 3 }}>{c.user}</div>
        </div>
        <span
          style={{
            background: rc.bg,
            color: rc.text,
            border: `1px solid ${rc.border}`,
            borderRadius: 8,
            padding: "4px 10px",
            fontSize: 11,
            fontWeight: 700,
          }}
        >
          {c.risk}
        </span>
      </div>

      {/* Middle Info */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span style={{ background: "#f1f5f9", padding: "3px 8px", borderRadius: 6, fontSize: 11, color: T.slate }}>{c.platform}</span>
        <span style={{ background: "#f1f5f9", padding: "3px 8px", borderRadius: 6, fontSize: 11, color: T.slate }}>{c.category}</span>
      </div>

      {/* Footer */}
      <div style={{ marginTop: "auto", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontSize: 11, color: T.muted }}>
          <Icon.Clock size={11} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
          {c.lastSignal}
        </div>
        {c.mine && (
          <span
            style={{
              background: "#eff6ff",
              color: T.indigo,
              border: "1px solid #bfdbfe",
              borderRadius: 4,
              fontSize: 9,
              padding: "2px 6px",
              fontWeight: 700,
            }}
          >
            ASSIGNED TO ME
          </span>
        )}
        {c.work_status && c.work_status !== "not_started" && (
          <WorkStatusBadge workStatus={c.work_status} />
        )}
      </div>
    </div>
  );
}

// ─── YOUTH HELPER PROFILE CARD ───────────────────────────────────────────────
function YouthHelperCard({ user, stats }) {
  const userInitials = user?.username?.split(" ").map(n => n[0]).join("").slice(0, 2) 
    || user?.name?.split(" ").map(n => n[0]).join("").slice(0, 2) 
    || "YH";

  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 16,
        border: "1px solid #e2e8f0",
        padding: 24,
        boxShadow: "0 2px 12px rgba(0,0,0,0.04)",
      }}
    >
      {/* Avatar & Name */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: "50%",
            background: `linear-gradient(135deg, ${T.indigo}, ${T.indigoDark})`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 20,
            fontWeight: 700,
            color: "#fff",
            boxShadow: "0 4px 12px rgba(6,114,203,0.3)",
          }}
        >
          {userInitials}
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 16, color: T.navyMid }}>{user?.username || user?.name || "Youth Helper"}</div>
          <div style={{ fontSize: 12, color: T.muted }}>{user?.role || "Youth Helper"}</div>
        </div>
      </div>

      {/* Stats Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ background: "#fef2f2", borderRadius: 10, padding: "12px 14px", textAlign: "center" }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: "#dc2626" }}>{stats.myCritical}</div>
          <div style={{ fontSize: 10, color: "#991b1b", fontWeight: 600, textTransform: "uppercase" }}>Critical</div>
        </div>
        <div style={{ background: "#fff7ed", borderRadius: 10, padding: "12px 14px", textAlign: "center" }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: "#ea580c" }}>{stats.myHigh}</div>
          <div style={{ fontSize: 10, color: "#c2410c", fontWeight: 600, textTransform: "uppercase" }}>High</div>
        </div>
        <div style={{ background: "#f0fdf4", borderRadius: 10, padding: "12px 14px", textAlign: "center" }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: "#16a34a" }}>{stats.myOther}</div>
          <div style={{ fontSize: 10, color: "#166534", fontWeight: 600, textTransform: "uppercase" }}>Med/Low</div>
        </div>
        <div style={{ background: "#eff6ff", borderRadius: 10, padding: "12px 14px", textAlign: "center" }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: T.indigo }}>{stats.assignedToMe}</div>
          <div style={{ fontSize: 10, color: T.indigoDark, fontWeight: 600, textTransform: "uppercase" }}>Total Mine</div>
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{ marginTop: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: T.muted, marginBottom: 10, textTransform: "uppercase" }}>Quick Actions</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px", fontSize: 12, color: T.slate, cursor: "pointer", display: "flex", alignItems: "center", gap: 8, textAlign: "left" }}>
            <Icon.FileText size={14} color={T.indigo} /> View My Reports
          </button>
          <button style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8, padding: "10px 12px", fontSize: 12, color: T.slate, cursor: "pointer", display: "flex", alignItems: "center", gap: 8, textAlign: "left" }}>
            <Icon.Calendar size={14} color={T.indigo} /> Schedule Follow-up
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── MAIN COMPONENT ──────────────────────────────────────────────────────────
export default function EnhancedDashboard({ currentUser }) {
  const { user: authUser, logout } = useAuth();
  const user = currentUser || authUser;

  const [activeTab, setActiveTab] = useState("all");
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showHelpMenu, setShowHelpMenu] = useState(false);

  // ─── Case Detail State ─────────────────────────────────────────────────────
  const [selectedCase, setSelectedCase] = useState(null);
  const [detailTab, setDetailTab] = useState("overview");
  const [workStatus, setWorkStatus] = useState(null);
  const [workStatusSaving, setWorkStatusSaving] = useState(false);
  const [caseHistory, setCaseHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);

  // ─── Chatbot State ─────────────────────────────────────────────────────────
  const [showChatbot, setShowChatbot] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([
    { role: "assistant", content: "Hello! I'm here to help you with case guidance based on SCS protocols. How can I assist you today?" }
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // ─── Fetch cases from API ──────────────────────────────────────────────────
  const fetchCases = useCallback(async () => {
    try {
      setLoading(true);
      const data = await caseAPI.getAllCases();

      const transformedCases = data.map((c) => ({
        id: c.case_id || c.id,
        code: c.case_id || c.id,
        user: c.username || c.social_handle || c.user_id || `@user_${c.case_id}`,
        risk: riskLevelToLabel(c.current_risk_score ? c.current_risk_score / 20 : c.risk_level || 3),
        riskLevel: c.current_risk_score ? Math.round(c.current_risk_score / 20) : c.risk_level || 3,
        score: c.current_risk_score || (c.risk_level || 3) * 20,
        current_risk_score: c.current_risk_score,
        category: c.current_category || c.category || c.primary_concern || "General",
        platform: c.platform || "Instagram",
        lastSignal: c.last_signal_at
          ? new Date(c.last_signal_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })
          : "Mar 10",
        assignee: c.assigned_helper || c.assigned_to || null,
        assigned_to: c.assigned_to,
        mine: c.assigned_to === user?.user_id || c.assigned_helper === user?.user_id,
        status: c.case_status || "active",
        work_status: c.work_status || "not_started",
        ai_explanation: c.ai_explanation || "",
        ai_explanation_paragraph: c.ai_explanation_paragraph || "",
        recommended_actions_paragraph: c.recommended_actions_paragraph || "",
        signals: c.ai_explanation_signals || (c.ai_explanation ? c.ai_explanation.split(/[\n•]/).filter(s => s.trim()).slice(0, 5) : []),
        youth: {
          name: c.user_id || "Unknown Youth",
          handle: `@${c.user_id || "unknown"}`,
          instagramUrl: `https://instagram.com/${c.user_id || "unknown"}`,
        },
      }));

      setCases(transformedCases);
    } catch (error) {
      console.error("Error fetching cases:", error);
      setDemoData();
    } finally {
      setLoading(false);
    }
  }, [user]);

  const setDemoData = () => {
    const demoCases = [
      { id: "CASE_2026_007", code: "CASE_2026_007", user: "@complex_case_07", risk: "CRITICAL", riskLevel: 5, score: 94.1, current_risk_score: 94.1, category: "Multiple Factors", platform: "Instagram", lastSignal: "Mar 10", assignee: user?.user_id, mine: true, work_status: "in_progress", ai_explanation_paragraph: "User shows multiple concerning signals including isolation language and mood deterioration.", signals: ["Frequent mentions of isolation", "Mood deterioration over time", "Decreased social engagement"], youth: { name: "complex_case_07", handle: "@complex_case_07" } },
      { id: "CASE_2026_002", code: "CASE_2026_002", user: "@vulnerable_user_02", risk: "HIGH", riskLevel: 4, score: 92.3, current_risk_score: 92.3, category: "Self Harm", platform: "Instagram", lastSignal: "Mar 10", assignee: user?.user_id, mine: true, work_status: "not_started", ai_explanation_paragraph: "Recent posts contain self-harm related keywords and expressions of hopelessness.", signals: ["Self-harm keywords detected", "Expressions of hopelessness", "Withdrawal from activities"], youth: { name: "vulnerable_user_02", handle: "@vulnerable_user_02" } },
      { id: "CASE_2026_010", code: "CASE_2026_010", user: "@needs_specialist_10", risk: "HIGH", riskLevel: 4, score: 91.8, current_risk_score: 91.8, category: "Complex Trauma", platform: "Instagram", lastSignal: "Mar 9", assignee: "helper_005", mine: false, work_status: "in_progress", ai_explanation_paragraph: "History indicates complex trauma patterns requiring specialist intervention.", signals: ["Complex trauma indicators", "Need for specialist support"], youth: { name: "needs_specialist_10", handle: "@needs_specialist_10" } },
      { id: "CASE_2026_001", code: "CASE_2026_001", user: "@at_risk_teen_01", risk: "MEDIUM", riskLevel: 3, score: 78.5, current_risk_score: 78.5, category: "Depression", platform: "Instagram", lastSignal: "Mar 9", assignee: null, mine: false, work_status: "not_started", ai_explanation_paragraph: "Consistent low mood indicators and withdrawal from social activities.", signals: ["Low mood indicators", "Social withdrawal"], youth: { name: "at_risk_teen_01", handle: "@at_risk_teen_01" } },
      { id: "CASE_2026_005", code: "CASE_2026_005", user: "@isolated_user_05", risk: "MEDIUM", riskLevel: 3, score: 71.4, current_risk_score: 71.4, category: "Social Isolation", platform: "TikTok", lastSignal: "Mar 9", assignee: user?.user_id, mine: true, work_status: "not_started", ai_explanation_paragraph: "Significant decrease in social interactions and expressions of loneliness.", signals: ["Decreased social interactions", "Loneliness expressions"], youth: { name: "isolated_user_05", handle: "@isolated_user_05" } },
      { id: "CASE_2026_012", code: "CASE_2026_012", user: "@anxious_teen_12", risk: "MEDIUM", riskLevel: 3, score: 68.2, current_risk_score: 68.2, category: "Anxiety", platform: "X", lastSignal: "Mar 8", assignee: null, mine: false, work_status: "not_started", ai_explanation_paragraph: "Anxiety-related language patterns and sleep disturbance mentions.", signals: ["Anxiety language patterns", "Sleep disturbance mentions"], youth: { name: "anxious_teen_12", handle: "@anxious_teen_12" } },
      { id: "CASE_2026_015", code: "CASE_2026_015", user: "@struggling_15", risk: "LOW", riskLevel: 2, score: 45.0, current_risk_score: 45.0, category: "Academic Stress", platform: "Reddit", lastSignal: "Mar 8", assignee: "helper_003", mine: false, work_status: "completed", ai_explanation_paragraph: "Academic stress expressions but maintaining positive coping strategies.", signals: ["Academic stress", "Positive coping present"], youth: { name: "struggling_15", handle: "@struggling_15" } },
      { id: "CASE_2026_018", code: "CASE_2026_018", user: "@lonely_teen_18", risk: "CRITICAL", riskLevel: 5, score: 96.2, current_risk_score: 96.2, category: "Self Harm", platform: "TikTok", lastSignal: "Mar 10", assignee: "helper_002", mine: false, work_status: "in_progress", ai_explanation_paragraph: "Critical self-harm indicators requiring immediate attention.", signals: ["Critical self-harm indicators", "Immediate attention required"], youth: { name: "lonely_teen_18", handle: "@lonely_teen_18" } },
    ];
    setCases(demoCases);
  };

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  // ─── Filter cases based on tab ─────────────────────────────────────────────
  const myAssignedCases = useMemo(() => cases.filter((c) => c.mine), [cases]);
  const displayCases = activeTab === "mine" ? myAssignedCases : cases;

  // ─── Stats ─────────────────────────────────────────────────────────────────
  const stats = useMemo(() => {
    const myCases = cases.filter((c) => c.mine);
    return {
      total: cases.length,
      critical: cases.filter((c) => c.risk === "CRITICAL").length,
      high: cases.filter((c) => c.risk === "HIGH").length,
      medium: cases.filter((c) => c.risk === "MEDIUM").length,
      low: cases.filter((c) => c.risk === "LOW").length,
      assignedToMe: myCases.length,
      myCritical: myCases.filter((c) => c.risk === "CRITICAL").length,
      myHigh: myCases.filter((c) => c.risk === "HIGH").length,
      myOther: myCases.filter((c) => c.risk === "MEDIUM" || c.risk === "LOW").length,
    };
  }, [cases]);

  // ─── Chart data ────────────────────────────────────────────────────────────
  const chartData = useMemo(() => {
    const riskData = [
      { name: "Critical", value: stats.critical, color: CHART_COLORS.critical },
      { name: "High", value: stats.high, color: CHART_COLORS.high },
      { name: "Moderate", value: stats.medium, color: CHART_COLORS.moderate },
      { name: "Low", value: stats.low, color: CHART_COLORS.low },
    ];

    const platformCounts = cases.reduce((acc, c) => {
      acc[c.platform] = (acc[c.platform] || 0) + 1;
      return acc;
    }, {});
    const platformData = Object.entries(platformCounts)
      .map(([platform, count]) => ({ platform, cases: count }))
      .sort((a, b) => b.cases - a.cases);

    // Weekly risk trend data (simulated)
    const trendData = [
      { day: "Mon", critical: 2, high: 4, moderate: 3, low: 1 },
      { day: "Tue", critical: 3, high: 3, moderate: 4, low: 2 },
      { day: "Wed", critical: 2, high: 5, moderate: 3, low: 1 },
      { day: "Thu", critical: 4, high: 4, moderate: 2, low: 2 },
      { day: "Fri", critical: 3, high: 6, moderate: 4, low: 1 },
      { day: "Sat", critical: 2, high: 3, moderate: 2, low: 3 },
      { day: "Sun", critical: stats.critical, high: stats.high, moderate: stats.medium, low: stats.low },
    ];

    return { riskData, platformData, trendData, total: cases.length };
  }, [cases, stats]);

  // ─── Open Case ─────────────────────────────────────────────────────────────
  const openCase = (c) => {
    // In "All Cases" tab, just show info - don't open detail
    if (activeTab === "all") {
      alert(`Case ${c.id}: ${c.category} - ${c.risk} risk\n\nTo view full details, go to "Assigned to Me" tab.`);
      return;
    }
    // In "Assigned to Me" tab, open full detail panel
    if (!c.mine && user?.role !== "Admin") {
      alert("You can only view detailed information for cases assigned to you.");
      return;
    }
    setSelectedCase(c);
    setWorkStatus(c.work_status || "not_started");
    setDetailTab("overview");
    fetchCaseHistory(c.id);
    fetchRecommendations(c);
  };

  // ─── Fetch Case History ────────────────────────────────────────────────────
  const fetchCaseHistory = async (caseId) => {
    try {
      setLoadingHistory(true);
      const data = await historyAPI.getCaseHistory(caseId);
      setCaseHistory(data.reverse());
    } catch (err) {
      console.error("Failed to load case history:", err);
      setCaseHistory([
        { timestamp: new Date().toISOString(), event_type: "case_created", description: "Case created from signal detection", user: "System" },
        { timestamp: new Date(Date.now() - 86400000).toISOString(), event_type: "signal_detected", description: "New risk signals detected", user: "AI System" },
      ]);
    } finally {
      setLoadingHistory(false);
    }
  };

  // ─── Fetch Recommendations ─────────────────────────────────────────────────
  const fetchRecommendations = async (c) => {
    setLoadingRecommendations(true);
    try {
      const response = await fetch(`${CHATBOT_SERVICE_URL}/api/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_id: c.id,
          category: c.category,
          risk_level: c.riskLevel,
          risk_score: c.score,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setRecommendations(data.recommendations || []);
      } else {
        throw new Error("Failed to fetch recommendations");
      }
    } catch (err) {
      console.error("Failed to fetch recommendations:", err);
      setRecommendations([
        "Review all detected signals and risk factors",
        "Consider reaching out with empathetic, non-judgmental messaging",
        "Document all interactions and observations in case notes",
        "If risk level increases or no response in 48h, consider escalation",
        "Consult with team lead for complex or unclear situations",
      ]);
    } finally {
      setLoadingRecommendations(false);
    }
  };

  // ─── Update Work Status ────────────────────────────────────────────────────
  const handleWorkStatusChange = async (newStatus) => {
    if (!selectedCase) return;
    setWorkStatusSaving(true);
    try {
      await caseAPI.updateCase(selectedCase.id, { work_status: newStatus });
      setWorkStatus(newStatus);
      setSelectedCase(prev => ({ ...prev, work_status: newStatus }));
      setCases(prev => prev.map(c => c.id === selectedCase.id ? { ...c, work_status: newStatus } : c));
    } catch (err) {
      console.error("Failed to update work status:", err);
      setWorkStatus(newStatus);
      setSelectedCase(prev => ({ ...prev, work_status: newStatus }));
      setCases(prev => prev.map(c => c.id === selectedCase.id ? { ...c, work_status: newStatus } : c));
    } finally {
      setWorkStatusSaving(false);
    }
  };

  // ─── Chatbot Handler ───────────────────────────────────────────────────────
  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userMessage = chatInput.trim();
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setChatLoading(true);

    try {
      const response = await fetch(`${CHATBOT_SERVICE_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          case_context: selectedCase ? {
            case_id: selectedCase.id,
            category: selectedCase.category,
            risk_level: selectedCase.risk,
            risk_score: selectedCase.score,
          } : null,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setChatMessages(prev => [...prev, { role: "assistant", content: data.response || data.message || "I'm here to help. Could you provide more context?" }]);
      } else {
        throw new Error("Failed to get response");
      }
    } catch (err) {
      let fallbackResponse = "Thank you for your question. Based on SCS protocols, I recommend reviewing the case signals carefully. Would you like help with a specific aspect?";
      const lower = userMessage.toLowerCase();
      if (lower.includes("bully")) {
        fallbackResponse = "**Approaching Bullying Cases:**\n\n1. **Assess severity** — Is it a single incident or repeated pattern?\n2. **Do not confront the perpetrator directly** — Focus on the youth's wellbeing first.\n3. **Reach out with warmth** — Use a non-judgmental, empathetic tone.\n4. **Document everything** — Note your outreach attempt and response.";
      } else if (lower.includes("escalat")) {
        fallbackResponse = "**Escalation Criteria (SCS Protocol):**\n\nEscalate if **any** of the following apply:\n- Youth expresses intent to self-harm or harm others\n- Youth mentions feeling unsafe at home\n- Risk score is 4+ AND no response within 48 hours\n- Multiple high-risk signals across platforms\n\n*When in doubt, escalate.*";
      } else if (lower.includes("outreach") || lower.includes("message")) {
        fallbackResponse = "**Recommended Outreach Templates:**\n\n*General:*\n\"Hi [Name], I'm [Your Name] from YOUTH(TH)CARE. I wanted to check in with you. You don't have to share anything — I'm just here to listen if you need.\"\n\n*Always personalise these.*";
      }
      setChatMessages(prev => [...prev, { role: "assistant", content: fallbackResponse }]);
    } finally {
      setChatLoading(false);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // ─── User initials ─────────────────────────────────────────────────────────
  const userInitials = user?.username?.split(" ").map(n => n[0]).join("").slice(0, 2) 
    || user?.name?.split(" ").map(n => n[0]).join("").slice(0, 2) 
    || "YH";

  // ─── RENDER ────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        fontFamily: "'Segoe UI', system-ui, sans-serif",
        background: T.bg,
        minHeight: "100vh",
        color: T.navy,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* ── TOP NAV ── */}
      <nav
        style={{
          background: "linear-gradient(135deg, #0a1628 0%, #0f172a 100%)",
          color: "#fff",
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              background: `linear-gradient(135deg, ${T.indigo}, ${T.indigoDark})`,
              width: 36,
              height: 36,
              borderRadius: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 2px 8px rgba(6, 114, 203, 0.3)",
            }}
          >
            <Icon.Shield size={20} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Singapore Children's Society</div>
            <div style={{ fontSize: 10, color: "#94a3b8", letterSpacing: "1.2px", textTransform: "uppercase" }}>
              YOUTH<sup>TH</sup>CARE
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <DataFreshnessIndicator />

          <button
            onClick={fetchCases}
            style={{
              background: "linear-gradient(135deg, #059669, #10b981)",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "#fff",
              borderRadius: 8,
              padding: "6px 14px",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Icon.Zap size={14} color="#fff" /> Refresh
          </button>

          {/* Help Menu */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setShowHelpMenu(!showHelpMenu)}
              style={{
                background: "rgba(255,255,255,0.1)",
                border: "1px solid rgba(255,255,255,0.2)",
                color: "#fff",
                borderRadius: 8,
                padding: "6px 14px",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <Icon.AlertCircle size={14} color="#fff" /> Help
            </button>
            {showHelpMenu && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 6px)",
                  right: 0,
                  background: "#fff",
                  borderRadius: 12,
                  boxShadow: "0 8px 30px rgba(0,0,0,0.18)",
                  width: 200,
                  zIndex: 100,
                  overflow: "hidden",
                }}
              >
                <div style={{ padding: "6px 0" }}>
                  <button
                    onClick={() => { setShowHelpMenu(false); logout && logout(); }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      background: "none",
                      border: "none",
                      padding: "10px 16px",
                      cursor: "pointer",
                      fontSize: 13,
                      color: "#dc2626",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <Icon.LogOut size={14} color="#dc2626" /> Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* User Badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "rgba(255,255,255,0.08)",
              padding: "5px 12px",
              borderRadius: 20,
              border: "1px solid rgba(255,255,255,0.15)",
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: `linear-gradient(135deg, ${T.indigo}, ${T.indigoDark})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: 700,
                color: "#fff",
              }}
            >
              {userInitials}
            </div>
            <div>
              <div style={{ fontSize: 13 }}>{user?.username || user?.name || "User"}</div>
              <div style={{ fontSize: 10, color: "#94a3b8" }}>{user?.role || "Youth Helper"}</div>
            </div>
          </div>
        </div>
      </nav>

      {/* ── PRIVACY BANNER ── */}
      <div
        style={{
          background: "#eef2ff",
          borderBottom: "1px solid #c7d2fe",
          padding: "6px 24px",
          fontSize: 11.5,
          color: "#4338ca",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <Icon.Lock size={12} color="#4338ca" /> <strong>Privacy Notice:</strong> This dashboard displays AI-generated risk assessments only. Original social media content is never stored or displayed.
      </div>

      {/* ── TABS ── */}
      <div style={{ background: "#fff", borderBottom: "1px solid #e2e8f0", padding: "0 24px" }}>
        <div style={{ display: "flex", gap: 0 }}>
          <button
            onClick={() => { setActiveTab("all"); setSelectedCase(null); }}
            style={{
              padding: "14px 24px",
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: activeTab === "all" ? 700 : 500,
              color: activeTab === "all" ? T.indigo : "#64748b",
              borderBottom: activeTab === "all" ? `3px solid ${T.indigo}` : "3px solid transparent",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <Icon.BarChart2 size={16} color={activeTab === "all" ? T.indigo : "#94a3b8"} />
            All Cases Overview
            <span style={{ background: "#e0e7ff", color: "#4338ca", borderRadius: 10, padding: "2px 10px", fontSize: 12 }}>{cases.length}</span>
          </button>
          <button
            onClick={() => { setActiveTab("mine"); setSelectedCase(null); }}
            style={{
              padding: "14px 24px",
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: activeTab === "mine" ? 700 : 500,
              color: activeTab === "mine" ? T.indigo : "#64748b",
              borderBottom: activeTab === "mine" ? `3px solid ${T.indigo}` : "3px solid transparent",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <Icon.User size={16} color={activeTab === "mine" ? T.indigo : "#94a3b8"} />
            Assigned to Me
            <span style={{ background: "#ddd6fe", color: "#5b21b6", borderRadius: 10, padding: "2px 10px", fontSize: 12 }}>{myAssignedCases.length}</span>
          </button>
        </div>
      </div>

      {/* ── MAIN BODY ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {loading ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", background: "#fff" }}>
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: "50%",
                  border: `3px solid ${T.indigo}`,
                  borderTopColor: "transparent",
                  animation: "spin 0.7s linear infinite",
                  margin: "0 auto 16px",
                }}
              />
              <div style={{ fontSize: 16, fontWeight: 600, color: T.navyMid }}>Loading cases...</div>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          </div>
        ) : activeTab === "all" ? (
          /* ════════════════════════════════════════════════════════════════════
             ALL CASES TAB - Dashboard Overview with Charts + Youth Helper Card
             ════════════════════════════════════════════════════════════════════ */
          <div style={{ flex: 1, display: "flex", padding: 24, gap: 24, overflow: "hidden" }}>
            {/* Left Sidebar - Youth Helper Profile */}
            <div style={{ width: 280, flexShrink: 0 }}>
              <YouthHelperCard user={user} stats={stats} />
            </div>

            {/* Main Content Area */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20, overflow: "auto" }}>
              {/* Stats Row */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
                {[
                  { label: "Total Cases", value: stats.total, color: T.indigo, bg: "#eff6ff", icon: "📋" },
                  { label: "Critical", value: stats.critical, color: T.danger, bg: "#fef2f2", icon: "🚨" },
                  { label: "High Risk", value: stats.high, color: "#ea580c", bg: "#fff7ed", icon: "⚠️" },
                  { label: "Med/Low", value: stats.medium + stats.low, color: T.success, bg: "#f0fdf4", icon: "✅" },
                ].map((s, i) => (
                  <div
                    key={i}
                    style={{
                      background: "#fff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 14,
                      padding: "18px 20px",
                      position: "relative",
                      overflow: "hidden",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
                    }}
                  >
                    <div style={{ position: "absolute", top: 0, left: 0, width: 4, height: "100%", background: s.color }} />
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div>
                        <div style={{ fontSize: 12, color: T.muted, marginBottom: 6 }}>{s.label}</div>
                        <div style={{ fontSize: 32, fontWeight: 800, color: s.color }}>{s.value}</div>
                      </div>
                      <div style={{ fontSize: 28, background: s.bg, padding: "10px", borderRadius: 10 }}>{s.icon}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Charts Row */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                {/* Risk Distribution Pie */}
                <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                  <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: T.navyMid }}>
                    Risk Distribution
                  </div>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie data={chartData.riskData} cx="50%" cy="50%" innerRadius={40} outerRadius={60} paddingAngle={3} dataKey="value">
                        {chartData.riskData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ display: "flex", justifyContent: "center", gap: 14, marginTop: 10, flexWrap: "wrap" }}>
                    {chartData.riskData.map((r, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11 }}>
                        <div style={{ width: 10, height: 10, borderRadius: 3, background: r.color }} />
                        <span style={{ color: T.slate }}>{r.name}: {r.value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Weekly Risk Trend */}
                <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                  <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: T.navyMid }}>
                    Weekly Risk Trend
                  </div>
                  <ResponsiveContainer width="100%" height={160}>
                    <AreaChart data={chartData.trendData}>
                      <XAxis dataKey="day" tick={{ fontSize: 10, fill: T.muted }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: T.muted }} axisLine={false} tickLine={false} width={28} />
                      <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 11 }} />
                      <Area type="monotone" dataKey="critical" stackId="1" stroke="#dc2626" fill="#fecaca" />
                      <Area type="monotone" dataKey="high" stackId="1" stroke="#ea580c" fill="#fed7aa" />
                      <Area type="monotone" dataKey="moderate" stackId="1" stroke="#ca8a04" fill="#fef08a" />
                      <Area type="monotone" dataKey="low" stackId="1" stroke="#16a34a" fill="#bbf7d0" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>

                {/* Platform Breakdown */}
                <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                  <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: T.navyMid }}>
                    By Platform
                  </div>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart data={chartData.platformData} layout="vertical">
                      <XAxis type="number" tick={{ fontSize: 10, fill: T.muted }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="platform" tick={{ fontSize: 11, fill: T.slate }} axisLine={false} tickLine={false} width={70} />
                      <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12 }} />
                      <Bar dataKey="cases" fill={T.indigo} radius={[0, 6, 6, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Case Cards Grid */}
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.navyMid, marginBottom: 14 }}>
                  All Active Cases ({cases.length})
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
                  {cases.map((c) => (
                    <CasePanelCard key={c.id} c={c} onClick={openCase} isSelected={false} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ════════════════════════════════════════════════════════════════════
             ASSIGNED TO ME TAB - Case List with Detail Panel
             ════════════════════════════════════════════════════════════════════ */
          <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
            {/* Left Panel: My Cases List + Stats */}
            <div
              style={{
                flex: selectedCase ? "0 0 50%" : 1,
                minWidth: selectedCase ? 460 : undefined,
                background: "#fff",
                borderRight: selectedCase ? "1px solid #e5e7eb" : "none",
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                transition: "all 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
            >
              {/* My Stats Summary */}
              {!selectedCase && (
                <div style={{ padding: 20, borderBottom: "1px solid #e2e8f0" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                    {[
                      { label: "My Cases", value: stats.assignedToMe, color: T.indigo, bg: "#eff6ff" },
                      { label: "Critical", value: stats.myCritical, color: T.danger, bg: "#fef2f2" },
                      { label: "High", value: stats.myHigh, color: "#ea580c", bg: "#fff7ed" },
                      { label: "Med/Low", value: stats.myOther, color: T.success, bg: "#f0fdf4" },
                    ].map((s, i) => (
                      <div
                        key={i}
                        style={{
                          background: s.bg,
                          borderRadius: 12,
                          padding: "14px 16px",
                          textAlign: "center",
                        }}
                      >
                        <div style={{ fontSize: 26, fontWeight: 800, color: s.color }}>{s.value}</div>
                        <div style={{ fontSize: 11, color: s.color, fontWeight: 600 }}>{s.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Case Cards */}
              <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
                {myAssignedCases.length === 0 ? (
                  <div style={{ textAlign: "center", padding: 60, color: T.muted }}>
                    <Icon.User size={40} color="#e2e8f0" />
                    <div style={{ fontSize: 16, fontWeight: 600, marginTop: 16, color: T.slate }}>No cases assigned to you yet</div>
                    <div style={{ fontSize: 13, marginTop: 6 }}>Cases will appear here when assigned by your supervisor.</div>
                  </div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: selectedCase ? "1fr" : "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
                    {myAssignedCases.map((c) => (
                      <CasePanelCard key={c.id} c={c} onClick={openCase} isSelected={selectedCase?.id === c.id} />
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right Panel: Case Detail */}
            {selectedCase && (
              <div
                style={{
                  flex: "0 0 50%",
                  maxWidth: 680,
                  minWidth: 420,
                  background: "#fff",
                  display: "flex",
                  flexDirection: "column",
                  overflow: "hidden",
                  transition: "all 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
                }}
              >
                {/* Scrollable Content */}
                <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
                  {/* Case Header */}
                  <div
                    style={{
                      background: "linear-gradient(135deg, #1e40af, #3b82f6)",
                      padding: "18px 24px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexShrink: 0,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <button
                        onClick={() => setSelectedCase(null)}
                        style={{
                          background: "rgba(255,255,255,0.15)",
                          border: "none",
                          borderRadius: 8,
                          width: 36,
                          height: 36,
                          cursor: "pointer",
                          color: "#fff",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <Icon.ArrowLeft size={18} />
                      </button>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontWeight: 700, fontSize: 16, color: "#fff" }}>{selectedCase.code}</span>
                          <RiskBadge level={selectedCase.riskLevel} score={selectedCase.current_risk_score} />
                        </div>
                        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.75)", marginTop: 3 }}>
                          {selectedCase.platform} · {selectedCase.lastSignal}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedCase(null)}
                      style={{
                        background: "rgba(255,255,255,0.15)",
                        border: "none",
                        borderRadius: 8,
                        padding: "8px 14px",
                        fontSize: 12,
                        fontWeight: 600,
                        color: "#fff",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 5,
                      }}
                    >
                      <Icon.X size={14} /> Close
                    </button>
                  </div>

                  {/* Work Status Bar */}
                  <div
                    style={{
                      padding: "12px 24px",
                      background: "#f8fafc",
                      borderBottom: "1px solid #f1f5f9",
                      display: "flex",
                      alignItems: "center",
                      gap: 20,
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 10, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase" }}>Work</span>
                      <WorkStatusBadge workStatus={workStatus || selectedCase.work_status} />
                      <select
                        value={workStatus || selectedCase.work_status || "not_started"}
                        onChange={(e) => handleWorkStatusChange(e.target.value)}
                        disabled={workStatusSaving}
                        style={{
                          fontSize: 11,
                          padding: "4px 8px",
                          borderRadius: 6,
                          border: "1px solid #e2e8f0",
                          background: "#fff",
                          cursor: "pointer",
                          fontWeight: 500,
                        }}
                      >
                        <option value="not_started">Not Started</option>
                        <option value="in_progress">In Progress</option>
                        <option value="to_review">To Review</option>
                        <option value="completed">Completed</option>
                      </select>
                      {workStatusSaving && <span style={{ fontSize: 11, color: "#94a3b8" }}>Saving…</span>}
                    </div>
                  </div>

                  {/* Detail Tabs */}
                  <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #f1f5f9", background: "#fff", flexShrink: 0, paddingLeft: 8 }}>
                    {[
                      { id: "overview", label: "Overview" },
                      { id: "timeline", label: "Timeline" },
                    ].map((t) => (
                      <button
                        key={t.id}
                        onClick={() => setDetailTab(t.id)}
                        style={{
                          padding: "12px 16px",
                          fontSize: 12,
                          fontWeight: detailTab === t.id ? 600 : 500,
                          color: detailTab === t.id ? "#1e40af" : "#64748b",
                          background: "none",
                          border: "none",
                          borderBottom: detailTab === t.id ? "2px solid #3b82f6" : "2px solid transparent",
                          cursor: "pointer",
                        }}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>

                  {/* Detail Content */}
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", overflowY: "auto", background: "#f8fafc" }}>
                    {detailTab === "overview" && (
                      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
                        {/* Privacy Notice */}
                        <div
                          style={{
                            background: "#f0f9ff",
                            border: "1px solid #bae6fd",
                            borderRadius: 12,
                            padding: "14px 16px",
                            display: "flex",
                            gap: 12,
                            alignItems: "flex-start",
                          }}
                        >
                          <Icon.Shield size={16} style={{ flexShrink: 0, color: "#0284c7", marginTop: 1 }} />
                          <div style={{ fontSize: 12, color: "#0369a1", lineHeight: 1.5 }}>
                            <strong>Privacy:</strong> AI-generated risk signals only. No raw social media posts or personal content is stored.
                          </div>
                        </div>

                        {/* Youth Profile Card */}
                        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, display: "flex", alignItems: "center", gap: 8, color: "#1e293b", borderBottom: "1px solid #f1f5f9", paddingBottom: 12 }}>
                            <Icon.User size={16} color="#3b82f6" /> Youth Profile
                          </div>
                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                            <div>
                              <div style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Handle</div>
                              <div style={{ fontSize: 14, fontWeight: 600, color: "#1e293b" }}>{selectedCase.user}</div>
                            </div>
                            <div>
                              <div style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Platform</div>
                              <div style={{ fontSize: 14, color: "#475569" }}>{selectedCase.platform}</div>
                            </div>
                            <div>
                              <div style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Category</div>
                              <div style={{ fontSize: 14, color: "#475569" }}>{selectedCase.category}</div>
                            </div>
                            <div>
                              <div style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", marginBottom: 4 }}>Last Signal</div>
                              <div style={{ fontSize: 14, color: "#475569" }}>{selectedCase.lastSignal}</div>
                            </div>
                          </div>
                        </div>

                        {/* Risk Assessment */}
                        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, display: "flex", alignItems: "center", gap: 8, color: "#1e293b", borderBottom: "1px solid #f1f5f9", paddingBottom: 12 }}>
                            <Icon.TrendingUp size={16} color="#dc2626" /> Risk Assessment
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                            <span style={{ fontSize: 32, fontWeight: 800, color: (RISK_COLORS[selectedCase.riskLevel] || RISK_COLORS[3]).text }}>
                              {selectedCase.current_risk_score?.toFixed(1) ?? "—"}
                              <span style={{ fontSize: 18, fontWeight: 400, color: "#94a3b8" }}>%</span>
                            </span>
                          </div>
                          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 6 }}>
                            {(RISK_COLORS[selectedCase.riskLevel] || RISK_COLORS[3]).label} risk · Category: {selectedCase.category}
                          </div>
                        </div>

                        {/* AI Explanation Signals */}
                        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, display: "flex", alignItems: "center", gap: 8, color: "#1e293b", borderBottom: "1px solid #f1f5f9", paddingBottom: 12 }}>
                            <Icon.Activity size={16} color={T.indigo} /> AI Explanation Signals
                            <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 400 }}>(why this was flagged)</span>
                          </div>
                          {selectedCase.ai_explanation_paragraph && (
                            <div style={{ background: "#f8fafc", borderLeft: `3px solid ${T.indigo}`, padding: "12px 14px", marginBottom: 14, borderRadius: "0 8px 8px 0" }}>
                              <p style={{ margin: 0, fontSize: 13, color: "#475569", lineHeight: 1.6 }}>{selectedCase.ai_explanation_paragraph}</p>
                            </div>
                          )}
                          <div style={{ fontWeight: 500, fontSize: 12, color: "#64748b", marginBottom: 8 }}>Key Signals Detected:</div>
                          {selectedCase.signals && selectedCase.signals.length > 0 ? (
                            selectedCase.signals.map((s, i) => (
                              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 0", borderBottom: i < selectedCase.signals.length - 1 ? "1px solid #f1f5f9" : "none" }}>
                                <span style={{ background: "#eef2ff", color: T.indigo, borderRadius: 6, width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, flexShrink: 0, marginTop: 1 }}>{i + 1}</span>
                                <span style={{ fontSize: 13, color: "#475569", lineHeight: 1.5 }}>{s}</span>
                              </div>
                            ))
                          ) : (
                            <div style={{ fontSize: 13, color: "#94a3b8", fontStyle: "italic" }}>No signals detected for this case.</div>
                          )}
                        </div>

                        {/* Recommended Actions */}
                        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
                          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 16, display: "flex", alignItems: "center", gap: 8, color: "#1e293b", borderBottom: "1px solid #f1f5f9", paddingBottom: 12 }}>
                            <Icon.Lightbulb size={16} color="#f59e0b" /> Recommended Actions
                            <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 400 }}>(AI-generated from protocols)</span>
                          </div>
                          {selectedCase.recommended_actions_paragraph && (
                            <div style={{ background: "#fffbeb", borderLeft: "3px solid #f59e0b", padding: "12px 14px", marginBottom: 14, borderRadius: "0 8px 8px 0" }}>
                              <p style={{ margin: 0, fontSize: 13, color: "#475569", lineHeight: 1.6 }}>{selectedCase.recommended_actions_paragraph}</p>
                            </div>
                          )}
                          {loadingRecommendations ? (
                            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 0", color: "#94a3b8", fontSize: 13 }}>
                              <div style={{ width: 16, height: 16, border: "2px solid #e2e8f0", borderTop: `2px solid ${T.indigo}`, borderRadius: "50%", animation: "spin 1s linear infinite" }} />
                              Generating recommendations...
                            </div>
                          ) : (
                            <>
                              <div style={{ fontWeight: 500, fontSize: 12, color: "#64748b", marginBottom: 8 }}>Suggested Actions:</div>
                              {recommendations.map((rec, i) => (
                                <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 0", borderBottom: i < recommendations.length - 1 ? "1px solid #f1f5f9" : "none" }}>
                                  <span style={{ background: "#fef3c7", color: "#92400e", borderRadius: 6, width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, flexShrink: 0, marginTop: 1 }}>{i + 1}</span>
                                  <span style={{ fontSize: 13, color: "#475569", lineHeight: 1.5 }}>{rec}</span>
                                </div>
                              ))}
                            </>
                          )}
                        </div>

                        {/* Ask AI Button */}
                        <button
                          onClick={() => setShowChatbot(true)}
                          style={{
                            background: `linear-gradient(135deg, ${T.indigo}, ${T.indigoDark})`,
                            border: "none",
                            borderRadius: 10,
                            padding: "14px 20px",
                            color: "#fff",
                            fontSize: 14,
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 8,
                            boxShadow: "0 4px 14px rgba(6,114,203,0.3)",
                          }}
                        >
                          <Icon.MessageSquare size={16} /> Ask AI for Guidance on This Case
                        </button>
                      </div>
                    )}

                    {detailTab === "timeline" && (
                      <div style={{ padding: "24px 28px", display: "flex", flexDirection: "column", gap: 16 }}>
                        {loadingHistory ? (
                          <div style={{ textAlign: "center", padding: 40, color: T.muted }}>Loading timeline...</div>
                        ) : caseHistory.length === 0 ? (
                          <div style={{ textAlign: "center", padding: 40, color: T.muted }}>No history available yet.</div>
                        ) : (
                          caseHistory.map((event, i) => (
                            <div key={i} style={{ background: "#fff", borderRadius: 10, border: "1px solid #e2e8f0", padding: "14px 16px", display: "flex", gap: 14 }}>
                              <div style={{ width: 10, height: 10, borderRadius: "50%", background: T.indigo, marginTop: 5, flexShrink: 0 }} />
                              <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, fontWeight: 600, color: T.navyMid, textTransform: "capitalize" }}>{event.event_type?.replace(/_/g, " ")}</div>
                                <div style={{ fontSize: 13, color: T.slate, marginTop: 4, lineHeight: 1.5 }}>{event.description}</div>
                                <div style={{ fontSize: 11, color: T.muted, marginTop: 6 }}>
                                  {new Date(event.timestamp).toLocaleString()} · {event.user || "System"}
                                </div>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── CHATBOT TOGGLE ── */}
      <button
        onClick={() => setShowChatbot((s) => !s)}
        style={{
          position: "fixed",
          bottom: 24,
          right: showChatbot ? 404 : 24,
          width: 56,
          height: 56,
          borderRadius: "50%",
          background: showChatbot ? "#dc2626" : `linear-gradient(135deg, ${T.indigo}, ${T.indigoDark})`,
          border: "none",
          color: "#fff",
          cursor: "pointer",
          boxShadow: "0 4px 18px rgba(6,114,203,0.4)",
          zIndex: 300,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "all 0.3s",
        }}
      >
        {showChatbot ? <Icon.X size={20} /> : <Icon.MessageSquare size={22} />}
      </button>

      {/* ── CHATBOT PANEL ── */}
      {showChatbot && (
        <div
          style={{
            position: "fixed",
            bottom: 0,
            right: 0,
            width: 380,
            height: "100vh",
            background: "#fff",
            boxShadow: "-4px 0 20px rgba(0,0,0,0.12)",
            zIndex: 250,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Chat Header */}
          <div
            style={{
              background: `linear-gradient(135deg, ${T.indigo}, ${T.indigoDark})`,
              padding: "16px 20px",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Icon.MessageSquare size={20} />
              <div>
                <div style={{ fontWeight: 700, fontSize: 14 }}>AI Case Assistant</div>
                <div style={{ fontSize: 11, opacity: 0.8 }}>SCS Protocol Guidance</div>
              </div>
            </div>
            <button onClick={() => setShowChatbot(false)} style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 6, padding: 6, cursor: "pointer", color: "#fff" }}>
              <Icon.X size={16} />
            </button>
          </div>

          {/* Chat Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
            {chatMessages.map((msg, i) => (
              <div key={i} style={{ alignSelf: msg.role === "user" ? "flex-end" : "flex-start", maxWidth: "85%" }}>
                <div
                  style={{
                    background: msg.role === "user" ? T.indigo : "#f1f5f9",
                    color: msg.role === "user" ? "#fff" : T.navyMid,
                    padding: "10px 14px",
                    borderRadius: msg.role === "user" ? "12px 12px 0 12px" : "12px 12px 12px 0",
                    fontSize: 13,
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div style={{ alignSelf: "flex-start", maxWidth: "85%" }}>
                <div style={{ background: "#f1f5f9", padding: "10px 14px", borderRadius: "12px 12px 12px 0", fontSize: 13, color: T.muted }}>Thinking...</div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Quick Actions */}
          <div style={{ padding: "8px 16px", borderTop: "1px solid #e2e8f0", display: "flex", gap: 6, flexWrap: "wrap" }}>
            {["Bullying guidance", "Escalation criteria", "Outreach templates"].map((q) => (
              <button
                key={q}
                onClick={() => { setChatInput(q); }}
                style={{ background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 16, padding: "6px 12px", fontSize: 11, color: T.slate, cursor: "pointer" }}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Chat Input */}
          <form onSubmit={handleChatSubmit} style={{ padding: "12px 16px", borderTop: "1px solid #e2e8f0", display: "flex", gap: 8 }}>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask about case guidance..."
              style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid #e2e8f0", fontSize: 13, outline: "none" }}
            />
            <button
              type="submit"
              disabled={chatLoading || !chatInput.trim()}
              style={{ background: T.indigo, border: "none", borderRadius: 8, padding: "10px 14px", color: "#fff", cursor: chatLoading || !chatInput.trim() ? "not-allowed" : "pointer", opacity: chatLoading || !chatInput.trim() ? 0.6 : 1 }}
            >
              <Icon.Send size={16} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
