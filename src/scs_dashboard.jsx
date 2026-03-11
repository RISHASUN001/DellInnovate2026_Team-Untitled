import { useState, useEffect, useRef, useCallback, useMemo } from "react";
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
} from "recharts";
import { useAuth } from "./auth/AuthContext.jsx";
import { Icon } from "./components/Icons.jsx";
import { caseAPI, historyAPI } from "./services/api.js";

// ─── SERVICE URLS (proxied via Vite dev server in dev; adjust for prod) ───────
const CASE_SERVICE_URL = "http://localhost:8003";
const CHATBOT_SERVICE_URL = "http://localhost:8000";
const MCP_SERVICE_URL = "http://localhost:8002";

// ─── CURRENT USER FALLBACK — used only if no auth prop provided ───────────────
// AUTH_SERVICE_CALL: In production this object comes from the auth context;
// the prop passed by main.jsx (AppRouter) always takes precedence.
const CURRENT_USER_FALLBACK = {
  user_id: "sarah_l",
  name: "Sarah Lim",
  role: "Youth Helper",
  avatar_initials: "SL",
  employee_id: "YH-001",
};

// ─── DATA ────────────────────────────────────────────────────────────
// MOCK_CASES removed - now fetching from MongoDB via API

const RISK_COLORS = {
  1: { bg: "#d1fae5", text: "#065f46", label: "Low" },
  2: { bg: "#dbeafe", text: "#1e40af", label: "Low-Med" },
  3: { bg: "#fef3c7", text: "#92400e", label: "Medium" },
  4: { bg: "#ffedd5", text: "#c2410c", label: "High" },
  5: { bg: "#fee2e2", text: "#991b1b", label: "Critical" },
};

// ─── DESIGN TOKENS ───────────────────────────────────────────────────
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

// ─── RISK COLOR MAPPINGS (string keys) ───────────────────────────────
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

const PRESET_QUESTIONS = [
  {
    label: "How to approach a bullying case",
    q: "How should I approach a case involving bullying? What's the recommended first step?",
  },
  {
    label: "Recommended outreach messages",
    q: "Can you suggest recommended outreach message templates I can adapt for initial contact?",
  },
  {
    label: "Escalation criteria",
    q: "What are the escalation criteria? When should I escalate a case?",
  },
  {
    label: "Follow-up timelines",
    q: "What are the recommended follow-up timelines for active cases?",
  },
  {
    label: "Resources to share",
    q: "What resources and referral links are available to share with youth or their families?",
  },
];

const CHATBOT_RESPONSES = {
  default:
    "Thank you for your question. Based on SCS protocols, I recommend reviewing the case signals carefully before deciding on next steps. All outreach decisions are yours — I'm here to guide, not to act. Would you like help with a specific aspect of this case?",
  bullying:
    "**Approaching Bullying Cases:**\n\n1. **Assess severity** — Is it a single incident or a repeated pattern? Check the AI signals for frequency and escalation.\n2. **Do not confront the perpetrator directly** — Focus on the youth's wellbeing first.\n3. **Reach out with warmth** — Use a non-judgmental, empathetic tone. Acknowledge their feelings before offering support.\n4. **Document everything** — Use the checklist to note your outreach attempt and response.\n5. **Involve school or platform** — If the bullying is on a school platform, coordinate with SCS school liaison.\n\n*Remember: You decide whether and how to reach out. AI assists prioritisation only.*",
  outreach:
    "**Recommended Outreach Message Templates:**\n\n*Template A (General):*\n\"Hi [Name], I'm [Your Name] from YOUTH(TH)CARE. I wanted to check in with you. You don't have to share anything you're not comfortable with — I'm just here to listen if you need.\"\n\n*Template B (After a difficult event):*\n\"I heard things have been a bit tough lately. Please know there are people who care, and support is available whenever you're ready.\"\n\n*Template C (Follow-up):*\n\"Just wanted to let you know I'm still here. No pressure — take your time.\"\n\n*Always personalise these. You know the context best.*",
  escalation:
    "**Escalation Criteria (SCS Protocol):**\n\nEscalate a case if **any** of the following apply:\n- Youth expresses intent to self-harm or harm others\n- Youth mentions feeling unsafe at home\n- Risk score is 4 or above AND outreach has not received a response within 48 hours\n- Multiple high-risk signals across different platforms\n- Youth is under 14 and the case involves any form of abuse\n\n**To escalate:** Use the 'Escalation considered' checklist item, add your notes, and notify your team lead.\n\n*When in doubt, escalate. Better safe than sorry.*",
  followup:
    "**Follow-Up Timelines (SCS Protocol):**\n\n| Risk Level | First Outreach | Follow-Up 1 | Follow-Up 2 | Review |\n|---|---|---|---|---|\n| Critical (5) | Within 2 hours | 24 hours | 48 hours | 72 hours |\n| High (4) | Within 6 hours | 48 hours | 72 hours | 1 week |\n| Medium (3) | Within 24 hours | 3 days | 1 week | 2 weeks |\n| Low-Med (2) | Within 48 hours | 1 week | 2 weeks | 1 month |\n| Low (1) | Within 1 week | 2 weeks | 1 month | Quarterly |\n\n*These are guidelines. Adjust based on the youth's response and comfort level.*",
  resources:
    "**Resources & Referrals Available:**\n\n**Samaritans of Singapore** — 1800-221-4444 (24/7)\n**Childcare Link** — counselling & mental health support\n**School Liaison Programme** — coordinate with school counsellors\n**Youthline (Hong Kong, for cross-regional cases)** — 2382 0000\n**SCS Online Support Portal** — secure messaging platform for youth\n**Community Mental Health Teams** — for home visits if needed\n\n*Always check with your team lead before sharing external resources. Ensure the youth and family consent.*",
};

function getChatbotResponse(input, attachedCase) {
  const lower = input.toLowerCase();
  let key = "default";
  if (lower.includes("bully")) key = "bullying";
  else if (
    lower.includes("outreach") ||
    lower.includes("message") ||
    lower.includes("template")
  )
    key = "outreach";
  else if (lower.includes("escalat")) key = "escalation";
  else if (lower.includes("follow")) key = "followup";
  else if (lower.includes("resource") || lower.includes("referral"))
    key = "resources";

  let prefix = "";
  if (attachedCase)
    prefix = `Reviewing case ${attachedCase.code} (${attachedCase.category}, Risk ${attachedCase.current_risk_score?.toFixed(1) ?? attachedCase.riskLevel}%):\n\n`;
  return prefix + CHATBOT_RESPONSES[key];
}

// ─── ONBOARDING STEPS ────────────────────────────────────────────────
const ONBOARDING_STEPS = [
  {
    title: "Welcome to SCS Youth Helper Dashboard",
    desc: "This guided walkthrough will teach you how to use the dashboard. All decisions about youth outreach remain yours — AI is here only to help you prioritise and guide.",
    target: "hero-welcome",
    step: 1,
    total: 12,
  },
  {
    title: "1. The All Cases Dashboard",
    desc: "This is your global view organized by category columns. Each column shows cases of the same type (Self-Harm, Bullying, etc.), ordered by priority (highest risk first). Each card shows risk level (colour-coded 1–5), platform, last signal time, status, and assigned helper. The top-right shows when data was last ingested (every 6 hours) for privacy and platform compliance. Original social media content is never stored.",
    target: "tab-all",
    step: 2,
    total: 12,
  },
  {
    title: "2. Understanding Risk Levels",
    desc: "Risk levels range from 1 (Low - green) to 5 (Critical - red). These color-coded badges help you quickly identify priority cases. Critical (5) requires immediate attention within 2 hours, while Low (1) can be monitored weekly. The AI calculates risk based on language patterns, frequency, and sentiment shifts.",
    target: "risk-badge",
    step: 3,
    total: 12,
    highlight: "risk-badge",
  },
  {
    title: "3. Case Status Indicators",
    desc: "Status badges show the current state: Active (needs attention), Escalated (flagged for urgent review), Monitoring (being watched), or Pending (unassigned). Escalated cases (red badge) require immediate team lead notification and appear at the top of your queue.",
    target: "status-badge",
    step: 4,
    total: 12,
    highlight: "status-badge",
  },
  {
    title: "4. Assigning & Accessing Cases",
    desc: "Unassigned cases show '—' in the helper column. When a case is assigned to you, it appears in your 'Assigned to Me' tab with full details. Summary-only visibility (All Cases) vs. full access (Assigned to Me) is a key privacy boundary.",
    target: "tab-assigned",
    step: 5,
    total: 12,
  },
  {
    title: "5. Your Primary Workspace",
    desc: "The 'Assigned to Me' tab is where you'll spend most of your time. Here you can see your cases and open them for detailed review. Click any case card to begin.",
    target: "workspace-panel",
    step: 6,
    total: 12,
  },
  {
    title: "6. Drag & Drop Reordering",
    desc: "In the 'Assigned to Me' tab, you can reorder cases by dragging and dropping them, just like in Jira. This helps you organize your workload according to your own priorities. The order you set is saved for your use.",
    target: "workspace-panel",
    step: 7,
    total: 12,
  },
  {
    title: "7. Youth Profile & Contact Info",
    desc: "Each case shows the youth's profile with their name, age, Instagram handle, and avatar. This helps you understand who you're supporting. The profile includes all necessary contact information while maintaining privacy protocols.",
    target: "youth-profile",
    step: 8,
    total: 12,
    highlight: "youth-profile",
  },
  {
    title: "8. Reach Out Button",
    desc: "The 'Reach Out via Instagram' button lets you initiate contact with the youth. Click this when you're ready to make contact after reviewing the case. IMPORTANT: Always review SCS outreach protocols and use trauma-informed language before reaching out.",
    target: "reach-out-button",
    step: 9,
    total: 12,
    highlight: "reach-out-button",
  },
  {
    title: "9. AI Signals & Risk Assessment",
    desc: "AI signals explain why a case was flagged. Each numbered signal shows specific patterns detected: distress keywords, sentiment shifts, temporal patterns, or behavioral changes. These are insights to guide your decision - you determine the appropriate action.",
    target: "case-detail-area",
    step: 10,
    total: 12,
  },
  {
    title: "10. The Checklist & Comments",
    desc: "Use the checklist to track mandatory steps: outreach attempted, response received, follow-up scheduled, escalation considered, and case closed. You can add comments and custom checklist items. Only you can see your edits.",
    target: "checklist-panel",
    step: 11,
    total: 12,
  },
  {
    title: "11. The Recommendation Chatbot",
    desc: "The chatbot at the bottom-right offers guidance based on SCS protocols. Use the paperclip icon to attach one of your assigned cases for context. Try the quick-action preset buttons for common questions. Remember: AI guides, you decide.",
    target: "chatbot-area",
    step: 12,
    total: 12,
  },
];

// ─── COMPONENTS ──────────────────────────────────────────────────────

function RiskBadge({ level, score }) {
  const c = RISK_COLORS[level] || {
    bg: "#f3f4f6",
    text: "#4b5563",
    label: "Unknown",
  };
  if (!level && !score) return null;
  const displayScore = score ? `${score.toFixed(1)}%` : `${c.label} (${level})`;
  return (
    <span
      style={{
        background: c.bg,
        color: c.text,
        padding: "3px 10px",
        borderRadius: 20,
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {displayScore}
    </span>
  );
}

function StatusBadge({ status }) {
  const map = {
    Active: ["#e0e7ff", "#3730a3"],
    Escalated: ["#fee2e2", "#991b1b"],
    Monitoring: ["#f3f4f6", "#4b5563"],
    Pending: ["#fef9c3", "#854d0e"],
  };
  const [bg, txt] = map[status] || ["#f3f4f6", "#4b5563"];
  return (
    <span
      style={{
        background: bg,
        color: txt,
        padding: "3px 10px",
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {status}
    </span>
  );
}

function DataFreshnessIndicator({ highlight }) {
  return (
    <div
      id="freshness-indicator"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        background: highlight ? "#fef3c7" : "rgba(255,255,255,0.08)",
        border: highlight
          ? "2px solid #f59e0b"
          : "1px solid rgba(255,255,255,0.15)",
        borderRadius: 10,
        padding: "8px 14px",
        transition: "all 0.4s",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Icon.RefreshCw size={14} color={highlight ? "#92400e" : "#cbd5e1"} />
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: highlight ? "#92400e" : "#cbd5e1",
              letterSpacing: "0.5px",
            }}
          >
            LAST INGESTION
          </div>
          <div
            style={{ fontSize: 12, color: highlight ? "#78350f" : "#94a3b8" }}
          >
            Today, 06:12 AM · Next in ~3h 48m
          </div>
        </div>
      </div>
      <div
        style={{
          width: 1,
          height: 30,
          background: highlight ? "#f59e0b" : "rgba(255,255,255,0.2)",
          margin: "0 4px",
        }}
      ></div>
      <div
        style={{
          fontSize: 10,
          color: highlight ? "#92400e" : "#94a3b8",
          maxWidth: 140,
          lineHeight: 1.35,
        }}
      >
        Data refreshes every <strong>6 hours</strong> for privacy & platform
        compliance. Original content is <strong>not stored</strong>.
      </div>
    </div>
  );
}

function CaseCard({
  c,
  onClick,
  highlight,
  isAssignedView,
  llmSummary,
  onViewSummary,
}) {
  const riskColor = RISK_COLORS[c.riskLevel] || {
    bg: "#f3f4f6",
    text: "#4b5563",
    label: "Unknown",
  };
  const hasSummary = llmSummary || c.llm_summary;
  // Extract LLM category tag from summary if present
  let llmTag =
    c.llm_tag ||
    (hasSummary && typeof hasSummary === "object" && hasSummary.category_tag) ||
    null;
  if (!llmTag && hasSummary && typeof hasSummary === "string") {
    // Try to parse tag from summary text
    const tagMatch = hasSummary.match(/category\s*:\s*([\w\s-]+)/i);
    if (tagMatch) llmTag = tagMatch[1].trim();
  }

  // Priority badge color
  const priorityColors = {
    critical: { bg: "#fef2f2", text: "#dc2626", border: "#fecaca" },
    high: { bg: "#fffbeb", text: "#d97706", border: "#fde68a" },
    medium: { bg: "#eff6ff", text: "#2563eb", border: "#bfdbfe" },
    low: { bg: "#f0fdf4", text: "#16a34a", border: "#bbf7d0" },
  };
  const pColor = priorityColors[c.priority] || priorityColors.medium;

  return (
    <div
      id={`case-card-${c.id}`}
      onClick={() => onClick(c)}
      style={{
        background: "#fff",
        borderRadius: 12,
        border: highlight ? "2px solid #3b82f6" : "1px solid #f1f5f9",
        padding: "14px 16px",
        cursor: "pointer",
        transition: "all 0.2s ease",
        boxShadow: highlight
          ? "0 0 0 3px rgba(59,130,246,0.15)"
          : "0 1px 4px rgba(0,0,0,0.04)",
        position: "relative",
        minWidth: 0,
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.boxShadow = "0 4px 16px rgba(0,0,0,0.08)")
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.boxShadow = highlight
          ? "0 0 0 3px rgba(59,130,246,0.15)"
          : "0 1px 4px rgba(0,0,0,0.04)")
      }
    >
      {/* Top row: Case ID + Priority Badge */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
        }}
      >
        <span
          style={{
            fontWeight: 700,
            fontSize: 14,
            color: "#1e293b",
            fontFamily: "monospace",
          }}
        >
          {c.code}
        </span>
        <span
          style={{
            background: pColor.bg,
            color: pColor.text,
            border: `1px solid ${pColor.border}`,
            padding: "3px 10px",
            borderRadius: 20,
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
          }}
        >
          {c.priority || "Medium"}
        </span>
      </div>

      {/* Second row: User ID, Risk Score, Risk Category */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 10,
          flexWrap: "wrap",
        }}
      >
        <span
          style={{
            fontSize: 10,
            color: "#64748b",
            background: "#f8fafc",
            padding: "2px 6px",
            borderRadius: 4,
          }}
        >
          {c.user_id || c.youth?.name || "—"}
        </span>
        <RiskBadge level={c.riskLevel} score={c.current_risk_score} />
        <StatusBadge status={c.status} />
      </div>

      {/* Info Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
          marginBottom: 10,
          fontSize: 11,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              color: "#94a3b8",
              fontSize: 9,
              marginBottom: 2,
              textTransform: "uppercase",
              letterSpacing: "0.4px",
            }}
          >
            Category
          </div>
          <div
            style={{
              color: "#334155",
              fontWeight: 600,
              fontSize: 11,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
            title={c.category}
          >
            {c.category}
          </div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              color: "#94a3b8",
              fontSize: 9,
              marginBottom: 2,
              textTransform: "uppercase",
              letterSpacing: "0.4px",
            }}
          >
            Platform
          </div>
          <div style={{ color: "#334155", fontWeight: 600, fontSize: 11 }}>
            {c.platform}
          </div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              color: "#94a3b8",
              fontSize: 9,
              marginBottom: 2,
              textTransform: "uppercase",
              letterSpacing: "0.4px",
            }}
          >
            Last Signal
          </div>
          <div style={{ color: "#334155", fontWeight: 600, fontSize: 11 }}>
            {c.lastSignal
              ? new Date(c.lastSignal).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })
              : "—"}
          </div>
        </div>
        <div style={{ minWidth: 0 }}>
          <div
            style={{
              color: "#94a3b8",
              fontSize: 9,
              marginBottom: 2,
              textTransform: "uppercase",
              letterSpacing: "0.4px",
            }}
          >
            Assigned To
          </div>
          <div style={{ color: "#334155", fontWeight: 600, fontSize: 11 }}>
            {c.assignedTo || c.assigned_to || "Unassigned"}
          </div>
        </div>
      </div>

      {/* Badges row */}
      <div
        style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 10 }}
      >
        {!isAssignedView && c.assignedToMe && (
          <span
            style={{
              background: "#3b82f6",
              color: "#fff",
              fontSize: 9,
              fontWeight: 600,
              padding: "2px 6px",
              borderRadius: 8,
            }}
          >
            MINE
          </span>
        )}
        {hasSummary && (
          <span
            onClick={(e) => {
              e.stopPropagation();
              if (onViewSummary) onViewSummary(c);
            }}
            style={{
              background: "linear-gradient(135deg, #059669, #10b981)",
              color: "#fff",
              fontSize: 9,
              fontWeight: 600,
              padding: "2px 6px",
              borderRadius: 8,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 3,
            }}
            title="View AI Summary"
          >
            <Icon.Zap size={9} color="#fff" /> AI
          </span>
        )}
      </div>

      {/* Brief summary */}
      <div
        style={{
          fontSize: 11,
          color: "#64748b",
          lineHeight: 1.5,
          borderTop: "1px solid #f1f5f9",
          paddingTop: 10,
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {c.ai_explanation_paragraph
          ? c.ai_explanation_paragraph.substring(0, 100) +
            (c.ai_explanation_paragraph.length > 100 ? "..." : "")
          : c.summary && c.summary.substring(0, 100)}
      </div>
    </div>
  );
}

function CaseStatusBadge({ caseStatus }) {
  const cfg = {
    new: { bg: "#eef2ff", text: "#3730a3", label: "New" },
    unassigned: { bg: "#fffbeb", text: "#92400e", label: "Unassigned" },
    assigned: { bg: "#d1fae5", text: "#065f46", label: "Assigned" },
    reassigned: {
      bg: "#fce7f3",
      text: "#9d174d",
      label: "Pending Reassignment",
    },
  };
  const c = cfg[caseStatus] || {
    bg: "#f3f4f6",
    text: "#4b5563",
    label: caseStatus || "—",
  };
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

function WorkStatusBadge({ workStatus }) {
  const cfg = {
    not_started: { bg: "#f3f4f6", text: "#4b5563", label: "Not Started" },
    in_progress: { bg: "#dbeafe", text: "#1e40af", label: "In Progress" },
    to_review: { bg: "#fee2e2", text: "#991b1b", label: "To Review" },
    completed: { bg: "#d1fae5", text: "#065f46", label: "Completed" },
  };
  const c = cfg[workStatus] || {
    bg: "#f3f4f6",
    text: "#4b5563",
    label: workStatus || "—",
  };
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
          <div style={{ fontWeight: 700, fontSize: 14, color: T.navyMid }}>{c.id || c.code}</div>
          <div style={{ fontSize: 13, color: T.slate, marginTop: 3 }}>{c.user || c.user_id || c.youth?.handle}</div>
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
          {c.risk || riskLevelToLabel(c.riskLevel || 3)}
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
        {(c.mine || c.assignedToMe) && (
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
  const userInitials =
    user?.username?.split(" ").map((n) => n[0]).join("").slice(0, 2) ||
    user?.name?.split(" ").map((n) => n[0]).join("").slice(0, 2) ||
    user?.avatar_initials ||
    "YH";

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
          <div style={{ fontWeight: 700, fontSize: 16, color: T.navyMid }}>
            {user?.username || user?.name || "Youth Helper"}
          </div>
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

// ─── MAIN APP (Youth Helper Dashboard) ──────────────────────────────
export default function YouthHelperDashboard({ currentUser: propUser }) {
  const { logout } = useAuth();
  // Prefer the prop from the router; fall back to local const for standalone use
  const currentUser = propUser || CURRENT_USER_FALLBACK;
  const currentUserHeaderId = (currentUser?.email || currentUser?.user_id || currentUser?.id || "")
    .toString()
    .trim();
  const currentUserIdentity = (currentUser?.email || currentUser?.user_id || currentUser?.id || "")
    .toString()
    .trim()
    .toLowerCase();

  const isAssignedToCurrentUser = (assignedTo) => {
    if (!assignedTo || !currentUserIdentity) return false;
    return assignedTo.toString().trim().toLowerCase() === currentUserIdentity;
  };
  const [activeTab, setActiveTab] = useState("all");
  const [selectedCase, setSelectedCase] = useState(null);
  const [detailTab, setDetailTab] = useState("overview"); // 'overview' | 'timeline'
  const [accessDeniedCase, setAccessDeniedCase] = useState(null); // case that triggered access denied
  // Work status state for open case
  const [workStatus, setWorkStatus] = useState(null);
  const [showToReviewPopup, setShowToReviewPopup] = useState(false);
  const [toReviewReason, setToReviewReason] = useState("");
  const [workStatusSaving, setWorkStatusSaving] = useState(false);
  // Reassignment request state
  const [showReassignPopup, setShowReassignPopup] = useState(false);
  const [reassignReason, setReassignReason] = useState("");
  const [reassignSaving, setReassignSaving] = useState(false);
  const [reassignMsg, setReassignMsg] = useState("");
  const [onboardingStep, setOnboardingStep] = useState(0); // 0 = show welcome modal
  const [onboardingActive, setOnboardingActive] = useState(true);
  const [onboardingDone, setOnboardingDone] = useState(false);
  const [showChatbot, setShowChatbot] = useState(false);
  const [showHelpMenu, setShowHelpMenu] = useState(false);
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // ── Live case data from MongoDB API ──
  const [cases, setCases] = useState([]);
  const [helpers, setHelpers] = useState([]); // Youth helpers from scs_users
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ── AI Recommendations ──
  const [recommendations, setRecommendations] = useState([]);
  const [loadingRecommendations, setLoadingRecommendations] = useState(false);

  // ── Case History (Timeline) ──
  const [caseHistory, setCaseHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // ── LLM Summary Integration ──
  const [llmSummaries, setLlmSummaries] = useState({});
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [expandedSummary, setExpandedSummary] = useState(null);
  const [summaryDialogOpen, setSummaryDialogOpen] = useState(false);
  const [selectedSummary, setSelectedSummary] = useState(null);

  useEffect(() => {
    const loadCases = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await caseAPI.getAllCases();

        // Fetch helpers to map assigned_to
        let helpersData = [];
        try {
          const {
            default: { userAPI },
          } = await import("./services/api.js");
          helpersData = await userAPI.getYouthHelpers();
          setHelpers(
            helpersData.map((h) => ({
              user_id: h.user_id,
              name: h.username,
              employee_id: h.user_id,
              department: h.role,
              avatar_initials:
                h.username
                  ?.split(" ")
                  .map((n) => n[0])
                  .join("") || h.user_id?.substring(0, 2).toUpperCase(),
            })),
          );
        } catch (err) {
          console.warn("Could not fetch helpers:", err);
        }

        // Transform API data to match the component's expected format
        const transformed = data.map((c) => {
          // Extract LLM tag/category from summary if present
          let llmTag =
            c.llm_tag ||
            (c.llm_summary &&
              typeof c.llm_summary === "object" &&
              c.llm_summary.category_tag) ||
            null;
          if (!llmTag && c.llm_summary && typeof c.llm_summary === "string") {
            const tagMatch = c.llm_summary.match(/category\s*:\s*([\w\s-]+)/i);
            if (tagMatch) llmTag = tagMatch[1].trim();
          }
          return {
            id: c.case_id,
            code: c.case_id,
            case_id: c.case_id,
            riskLevel: c.current_risk_score
              ? Math.round(c.current_risk_score / 20)
              : 3,
            current_risk_score: c.current_risk_score,
            category: llmTag || c.current_category || c.category || "Unknown",
            llm_tag: llmTag || c.current_category,
            platform: c.platform || "Instagram",
            lastSignal: c.last_signal_at || c.updated_at || "—",
            status: c.case_status || "Active",
            case_status: c.case_status,
            work_status: c.work_status,
            priority: c.priority || "medium",
            assigned_to: c.assigned_to,
            assignedTo: c.assigned_to || "—",
            assignedToMe: isAssignedToCurrentUser(c.assigned_to),
            created_at: c.created_at,
            updated_at: c.updated_at,
            user_id: c.user_id,
            youth: {
              name: c.user_id || "Unknown Youth",
              age: "—",
              avatar: "U",
              handle: `@${c.user_id || "unknown"}`,
              instagramUrl: `https://instagram.com/${c.user_id || "unknown"}`,
            },
            signals: c.ai_explanation_signals
              ? c.ai_explanation_signals
              : c.ai_explanation
                ? c.ai_explanation
                    .split(/[\n•]/)
                    .filter(
                      (s) =>
                        s.trim() &&
                        (s.includes(":") || s.includes("-") || s.length > 15),
                    )
                    .map((s) => s.replace(/^[•\-]\s*/, "").trim())
                    .filter(
                      (s) =>
                        s &&
                        !s.toLowerCase().startsWith("this case") &&
                        !s.toLowerCase().startsWith("key signals"),
                    )
                : c.current_risk_signals
                  ? c.current_risk_signals
                      .split(",")
                      .map((s) => s.trim())
                      .filter((s) => s)
                  : [],
            ai_explanation_paragraph: c.ai_explanation_paragraph || "",
            recommended_actions_paragraph:
              c.recommended_actions_paragraph || "",
            summary:
              c.llm_summary && typeof c.llm_summary === "string"
                ? c.llm_summary
                : c.ai_explanation_paragraph ||
                  c.ai_explanation ||
                  "No summary available",
            llm_summary: c.llm_summary,
            ai_explanation: c.ai_explanation,
            recommendations: c.recommended_actions || c.recommendations || [],
            needs_review: c.needs_review || false,
          };
        });

        setCases(transformed);

        // Also fetch LLM summaries for quick access
        try {
          const summariesRes = await fetch(
            `${CASE_SERVICE_URL.replace(":8003", ":8004")}/api/analytics/llm-summaries?limit=50`,
          );
          if (summariesRes.ok) {
            const summariesData = await summariesRes.json();
            const summariesMap = {};
            (summariesData.summaries || []).forEach((summary) => {
              summariesMap[summary.case_user] = summary;
            });
            setLlmSummaries(summariesMap);
          }
        } catch (summaryErr) {
          console.warn("Could not fetch LLM summaries:", summaryErr);
        }
      } catch (err) {
        setError(err.message || "Failed to load cases");
        console.error("Error loading cases:", err);
      } finally {
        setLoading(false);
      }
    };

    loadCases();
  }, [currentUser]);

  // Fetch recommendations when a case is selected
  useEffect(() => {
    const fetchRecommendations = async () => {
      if (!selectedCase) {
        setRecommendations([]);
        return;
      }

      // First check if case already has LLM-generated recommendations from MongoDB
      if (
        selectedCase.recommendations &&
        selectedCase.recommendations.length > 0
      ) {
        setRecommendations(selectedCase.recommendations);
        return;
      }

      // Only fetch from chatbot API for assigned cases without existing recommendations
      if (!selectedCase.assignedToMe) {
        setRecommendations([]);
        return;
      }

      try {
        setLoadingRecommendations(true);
        const {
          default: { chatbotAPI },
        } = await import("./services/api.js");

        // Prepare case info for the chatbot
        const caseInfo = {
          code: selectedCase.code,
          category: selectedCase.category,
          riskLevel: selectedCase.riskLevel,
          risk_label: (RISK_COLORS[selectedCase.riskLevel] || RISK_COLORS[3])
            .label,
          current_risk_score: selectedCase.current_risk_score,
          status: selectedCase.status,
          signals: selectedCase.signals,
        };

        const response = await chatbotAPI.getRecommendations(caseInfo);
        setRecommendations(response.recommendations || []);
      } catch (err) {
        console.error("Error fetching recommendations:", err);
        setRecommendations([]);
      } finally {
        setLoadingRecommendations(false);
      }
    };

    fetchRecommendations();
  }, [selectedCase]);

  const [assignedCasesOrder, setAssignedCasesOrder] = useState([]);
  // Keep order in sync when cases update
  useEffect(() => {
    const assignedIds = cases.filter((c) => c.assignedToMe).map((c) => c.id);
    setAssignedCasesOrder((prev) => {
      const merged = [...new Set([...prev, ...assignedIds])].filter((id) =>
        assignedIds.includes(id),
      );
      return merged;
    });
  }, [cases]);

  const myAssignedCases = assignedCasesOrder
    .map((id) => cases.find((c) => c.id === id))
    .filter(Boolean);
  const needsReviewCases = cases.filter((c) => c.needs_review || c.needsReview);

  // Group cases by category for All Cases view
  const casesByCategory = cases.reduce((acc, c) => {
    if (!acc[c.category]) acc[c.category] = [];
    acc[c.category].push(c);
    return acc;
  }, {});

  // Sort each category by priority (risk level descending)
  Object.keys(casesByCategory).forEach((category) => {
    casesByCategory[category].sort((a, b) => b.riskLevel - a.riskLevel);
  });

  // Get sorted categories (by highest risk level in each category)
  const sortedCategories = Object.keys(casesByCategory).sort((a, b) => {
    const maxRiskA = Math.max(...casesByCategory[a].map((c) => c.riskLevel));
    const maxRiskB = Math.max(...casesByCategory[b].map((c) => c.riskLevel));
    return maxRiskB - maxRiskA;
  });

  // ── Enhanced Dashboard Stats ──
  const stats = useMemo(() => {
    return {
      total: cases.length,
      critical: cases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "CRITICAL").length,
      high: cases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "HIGH").length,
      medium: cases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "MEDIUM").length,
      low: cases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "LOW").length,
      assignedToMe: myAssignedCases.length,
      myCritical: myAssignedCases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "CRITICAL").length,
      myHigh: myAssignedCases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "HIGH").length,
      myOther: myAssignedCases.filter((c) => {
        const r = c.risk || riskLevelToLabel(c.riskLevel || 3);
        return r === "MEDIUM" || r === "LOW";
      }).length,
    };
  }, [cases, myAssignedCases]);

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

    const trendData = [
      { day: "Mon", critical: 2, high: 4, moderate: 3, low: 1 },
      { day: "Tue", critical: 3, high: 3, moderate: 4, low: 2 },
      { day: "Wed", critical: 2, high: 5, moderate: 3, low: 1 },
      { day: "Thu", critical: 4, high: 4, moderate: 2, low: 2 },
      { day: "Fri", critical: 3, high: 6, moderate: 4, low: 1 },
      { day: "Sat", critical: 2, high: 3, moderate: 2, low: 3 },
      { day: "Sun", critical: stats.critical, high: stats.high, moderate: stats.medium, low: stats.low },
    ];

    const myRiskData = [
      { name: "Critical", value: myAssignedCases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "CRITICAL").length, color: CHART_COLORS.critical },
      { name: "High", value: myAssignedCases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "HIGH").length, color: CHART_COLORS.high },
      { name: "Moderate", value: myAssignedCases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "MEDIUM").length, color: CHART_COLORS.moderate },
      { name: "Low", value: myAssignedCases.filter((c) => (c.risk || riskLevelToLabel(c.riskLevel || 3)) === "LOW").length, color: CHART_COLORS.low },
    ];

    const myCategoryCounts = myAssignedCases.reduce((acc, c) => {
      acc[c.category] = (acc[c.category] || 0) + 1;
      return acc;
    }, {});
    const myCategoryData = Object.entries(myCategoryCounts)
      .map(([category, count]) => ({ category, cases: count }))
      .sort((a, b) => b.cases - a.cases);

    const myWorkStatusData = [
      { name: "Not Started", value: myAssignedCases.filter((c) => (c.work_status || "not_started") === "not_started").length, color: "#94a3b8" },
      { name: "In Progress", value: myAssignedCases.filter((c) => c.work_status === "in_progress").length, color: "#3b82f6" },
      { name: "To Review", value: myAssignedCases.filter((c) => c.work_status === "to_review").length, color: "#f59e0b" },
      { name: "Completed", value: myAssignedCases.filter((c) => c.work_status === "completed").length, color: "#10b981" },
    ];

    return { riskData, platformData, trendData, myRiskData, myCategoryData, myWorkStatusData };
  }, [cases, myAssignedCases, stats]);

  // Drag and drop handlers
  const handleDragStart = (index, e) => {
    // Add slight delay to distinguish clicks from drags
    setTimeout(() => {
      setDraggedIndex(index);
      setIsDragging(true);
    }, 100);
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const newOrder = [...assignedCasesOrder];
    const draggedId = newOrder[draggedIndex];
    newOrder.splice(draggedIndex, 1);
    newOrder.splice(index, 0, draggedId);

    setAssignedCasesOrder(newOrder);
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setTimeout(() => setIsDragging(false), 50);
  };

  const handleCaseClick = (c) => {
    // Only open case if not actively dragging
    if (!isDragging) {
      setSelectedCase(c);
    }
  };

  // ── LLM Summary Handlers ──
  const handleGenerateSummaries = async () => {
    setGeneratingSummary(true);
    try {
      const response = await fetch(
        `${CASE_SERVICE_URL.replace(":8003", ":8004")}/api/analytics/generate-llm-summaries?limit=10`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        },
      );
      if (response.ok) {
        alert(
          "LLM summary generation started in background. It may take a few minutes.",
        );
        // Refresh data after 30 seconds to show new summaries
        setTimeout(async () => {
          try {
            const summariesRes = await fetch(
              `${CASE_SERVICE_URL.replace(":8003", ":8004")}/api/analytics/llm-summaries?limit=50`,
            );
            if (summariesRes.ok) {
              const data = await summariesRes.json();
              const summariesMap = {};
              (data.summaries || []).forEach((summary) => {
                summariesMap[summary.case_user] = summary;
              });
              setLlmSummaries(summariesMap);
            }
          } catch (e) {
            console.error("Error refreshing summaries:", e);
          }
        }, 30000);
      } else {
        alert("Failed to start summary generation. Please try again.");
      }
    } catch (error) {
      console.error("Error generating summaries:", error);
      alert("Failed to start summary generation. Please try again.");
    } finally {
      setGeneratingSummary(false);
    }
  };

  const handleViewSummary = (caseItem) => {
    const summary =
      caseItem.llm_summary ||
      llmSummaries[caseItem.case_user || caseItem.user_id];
    if (summary) {
      setSelectedSummary({
        ...summary,
        case_user: caseItem.case_user || caseItem.user_id,
      });
      setSummaryDialogOpen(true);
    }
  };

  const handleGenerateSingleSummary = async (username) => {
    try {
      const response = await fetch(
        `${CASE_SERVICE_URL.replace(":8003", ":8004")}/api/analytics/generate-summary/${username}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        },
      );
      if (response.ok) {
        alert(`Summary generation started for ${username}`);
        // Refresh after 15 seconds
        setTimeout(async () => {
          try {
            const summariesRes = await fetch(
              `${CASE_SERVICE_URL.replace(":8003", ":8004")}/api/analytics/llm-summaries/${username}`,
            );
            if (summariesRes.ok) {
              const data = await summariesRes.json();
              if (data.summaries && data.summaries.length > 0) {
                setLlmSummaries((prev) => ({
                  ...prev,
                  [username]: data.summaries[0],
                }));
              }
            }
          } catch (e) {
            console.error("Error refreshing summary:", e);
          }
        }, 15000);
      } else {
        alert("Failed to generate summary");
      }
    } catch (error) {
      console.error("Error generating summary:", error);
      alert("Failed to generate summary");
    }
  };

  // Sync workStatus when case changes
  useEffect(() => {
    if (selectedCase) {
      setWorkStatus(
        selectedCase.work_status || selectedCase.workStatus || "not_started",
      );
      setDetailTab("overview");
    }
  }, [selectedCase?.case_id || selectedCase?.id]);

  const openCase = (c) => {
    // Strict: helpers may not open cases not assigned to them
    const isAssigned = c.assignedToMe || isAssignedToCurrentUser(c.assigned_to);
    if (!isAssigned && currentUser.role !== "Admin") {
      setAccessDeniedCase(c);
      return;
    }
    setSelectedCase(c);
  };

  const saveWorkStatus = async (newWs) => {
    setWorkStatusSaving(true);
    const caseId = selectedCase.case_id || selectedCase.code;
    try {
      // Update work status
      const res = await fetch(`${CASE_SERVICE_URL}/cases/${caseId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": (currentUser?.email || currentUser?.user_id || currentUser?.id || "").toString(),
          "X-User-Email": (currentUser?.email || "").toString(),
          "X-User-Role": currentUser.role,
        },
        body: JSON.stringify({ work_status: newWs }),
      });

      if (!res.ok) {
        throw new Error(`Failed to update work status: ${res.status}`);
      }

      const data = await res.json();

      setWorkStatus(data.work_status);
      setSelectedCase((prev) => ({
        ...prev,
        work_status: data.work_status,
        needs_review: newWs === "to_review",
      }));

      // Refresh case list
      setCases((prev) =>
        prev.map((c) =>
          (c.case_id || c.code) === caseId
            ? {
                ...c,
                work_status: data.work_status,
                needs_review: newWs === "to_review",
              }
            : c,
        ),
      );

      return { success: true, data };
    } catch (err) {
      console.error("Error saving work status:", err);
      alert("Failed to update work status. Please try again.");
      return { success: false, error: err };
    } finally {
      setWorkStatusSaving(false);
    }
  };

  const handleWorkStatusChange = async (newWs) => {
    if (newWs === "to_review") {
      // First, persist the work_status change to database
      setWorkStatus(newWs);
      const result = await saveWorkStatus(newWs);

      // After successful persistence, show popup for comment
      if (result.success) {
        setToReviewReason("");
        setShowToReviewPopup(true);
      }
    } else {
      setWorkStatus(newWs);
      await saveWorkStatus(newWs);
    }
  };

  const submitToReview = async () => {
    if (!toReviewReason.trim()) return;

    // Submit review request with the reason to scs_review_requests table
    const caseId = selectedCase.case_id || selectedCase.code;
    try {
      const reviewRes = await fetch(
        `${CASE_SERVICE_URL}/cases/${caseId}/review-request`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-Id": currentUserHeaderId,
            "X-User-Email": (currentUser?.email || "").toString(),
            "X-User-Role": currentUser.role,
          },
          body: JSON.stringify({ reason: toReviewReason.trim() }),
        },
      );

      if (!reviewRes.ok) {
        const errorText = await reviewRes.text();
        console.error("Failed to submit review request:", errorText);
        alert("Failed to submit review request. Please try again.");
        return;
      }

      // Success - close popup and show confirmation
      setShowToReviewPopup(false);
      setToReviewReason("");
      alert("Review request submitted successfully. Admin will be notified.");
    } catch (err) {
      console.error("Error submitting review request:", err);
      alert("Failed to submit review request. Please try again.");
    }
  };

  const submitReassignRequest = async () => {
    if (!reassignReason.trim()) return;
    setReassignSaving(true);
    const caseId = selectedCase.case_id || selectedCase.code;
    try {
      const res = await fetch(
        `${CASE_SERVICE_URL}/cases/${caseId}/reassignment-request`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-Id": currentUserHeaderId,
            "X-User-Email": (currentUser?.email || "").toString(),
            "X-User-Role": currentUser.role,
          },
          body: JSON.stringify({ reason: reassignReason.trim() }),
        },
      );
      if (res.ok) {
        setReassignMsg(
          "Reassignment request submitted. Admin will review your request.",
        );
        setSelectedCase((prev) => ({ ...prev, case_status: "reassigned" }));
      } else {
        setReassignMsg("Request saved locally (API unavailable).");
      }
    } catch {
      setReassignMsg("Request noted locally (API unavailable).");
    } finally {
      setReassignSaving(false);
      setShowReassignPopup(false);
      setReassignReason("");
    }
  };

  // Auto-advance onboarding context
  useEffect(() => {
    if (!onboardingActive || onboardingDone) return;
    if (onboardingStep === 1) setActiveTab("all");
    if (onboardingStep === 2) setActiveTab("all");
    if (onboardingStep === 3) {
      setActiveTab("all");
      if (cases.length > 0) setSelectedCase(cases[0]);
    }
    if (onboardingStep === 4) {
      setActiveTab("all");
      if (cases.length > 0) setSelectedCase(cases[0]);
    }
    if (onboardingStep === 5) setActiveTab("assigned");
    if (onboardingStep === 6) setActiveTab("assigned");
    if (onboardingStep === 7) setActiveTab("assigned");
    if (onboardingStep === 8) {
      setActiveTab("assigned");
      if (myAssignedCases.length > 0) setSelectedCase(myAssignedCases[0]);
    }
    if (onboardingStep === 9) {
      setActiveTab("assigned");
      if (myAssignedCases.length > 0) setSelectedCase(myAssignedCases[0]);
    }
    if (onboardingStep === 10) {
      setActiveTab("assigned");
      if (myAssignedCases.length > 0) setSelectedCase(myAssignedCases[0]);
    }
    if (onboardingStep === 11) {
      setActiveTab("assigned");
      if (myAssignedCases.length > 0) setSelectedCase(myAssignedCases[0]);
    }
    if (onboardingStep === 12) {
      if (myAssignedCases.length > 0) setSelectedCase(myAssignedCases[0]);
      setShowChatbot(true);
    }
  }, [onboardingStep]);

  const highlightTarget =
    onboardingActive && !onboardingDone
      ? ONBOARDING_STEPS[onboardingStep]?.highlight ||
        ONBOARDING_STEPS[onboardingStep]?.target
      : null;

  return (
    <div
      style={{
        fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif",
        background: "#f8fafc",
        backgroundImage: "url('/background.png')",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundAttachment: "fixed",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        fontSize: 14,
        color: "#1e293b",
        position: "relative",
        overflow: "hidden",
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
          position: "relative",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              background: "linear-gradient(135deg, #0672CB, #0460a9)",
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
            <div
              style={{ fontWeight: 700, fontSize: 15, letterSpacing: "0.3px" }}
            >
              Singapore Children's Society
            </div>
            <div
              style={{
                fontSize: 10,
                color: "#94a3b8",
                letterSpacing: "1.2px",
                textTransform: "uppercase",
              }}
            >
              YOUTH<sup>TH</sup>CARE
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <DataFreshnessIndicator highlight={highlightTarget === "tab-all"} />
          {/* Generate LLM Summaries Button */}
          <button
            onClick={handleGenerateSummaries}
            disabled={generatingSummary}
            style={{
              background: generatingSummary
                ? "rgba(255,255,255,0.05)"
                : "linear-gradient(135deg, #059669, #10b981)",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "#fff",
              borderRadius: 8,
              padding: "6px 14px",
              cursor: generatingSummary ? "not-allowed" : "pointer",
              fontSize: 13,
              fontWeight: 600,
              display: "flex",
              alignItems: "center",
              gap: 6,
              opacity: generatingSummary ? 0.7 : 1,
            }}
          >
            <Icon.Zap size={14} color="#fff" />{" "}
            {generatingSummary ? "Generating..." : "AI Summaries"}
          </button>
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
                  width: 220,
                  zIndex: 100,
                  overflow: "hidden",
                }}
              >
                <div style={{ padding: "6px 0" }}>
                  <button
                    onClick={() => {
                      setOnboardingActive(true);
                      setOnboardingDone(false);
                      setOnboardingStep(0);
                      setShowHelpMenu(false);
                    }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      background: "none",
                      border: "none",
                      padding: "10px 16px",
                      cursor: "pointer",
                      fontSize: 13,
                      color: "#1e293b",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "#f1f5f9")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "none")
                    }
                  >
                    <Icon.Monitor size={14} color="#475569" /> Run Onboarding
                  </button>
                  <button
                    onClick={() => {
                      setShowHelpMenu(false);
                    }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      background: "none",
                      border: "none",
                      padding: "10px 16px",
                      cursor: "pointer",
                      fontSize: 13,
                      color: "#1e293b",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "#f1f5f9")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "none")
                    }
                  >
                    <Icon.FileText size={14} color="#475569" /> User Guide
                  </button>
                  <button
                    onClick={() => {
                      setShowHelpMenu(false);
                    }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      background: "none",
                      border: "none",
                      padding: "10px 16px",
                      cursor: "pointer",
                      fontSize: 13,
                      color: "#1e293b",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "#f1f5f9")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "none")
                    }
                  >
                    <Icon.MessageSquare size={14} color="#475569" /> Contact
                    Support
                  </button>
                  <div
                    style={{ borderTop: "1px solid #f1f5f9", margin: "4px 0" }}
                  />
                  <button
                    onClick={() => {
                      setShowHelpMenu(false);
                      logout();
                    }}
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
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "#fef2f2")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = "none")
                    }
                  >
                    <Icon.LogOut size={14} color="#dc2626" /> Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
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
                background: "linear-gradient(135deg,#0672CB,#0460a9)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 11,
                fontWeight: 700,
                color: "#fff",
              }}
            >
              {currentUser.avatar_initials ||
                currentUser.name
                  ?.split(" ")
                  .map((n) => n[0])
                  .join("")
                  .slice(0, 2) ||
                "?"}
            </div>
            <div>
              <div style={{ fontSize: 13 }}>{currentUser.name}</div>
              <div style={{ fontSize: 10, color: "#94a3b8" }}>
                {currentUser.employee_id || ""} · {currentUser.role}
              </div>
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
        <Icon.Lock size={12} color="#4338ca" /> <strong>Privacy Notice:</strong>{" "}
        This dashboard displays AI-generated risk assessments only. Original
        social media content is never stored or displayed. All outreach
        decisions are made by you. Your edits and interactions are private to
        your account.
      </div>

      {/* ── ACCESS DENIED MODAL ── */}
      {accessDeniedCase && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.7)",
            zIndex: 500,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 18,
              width: 420,
              padding: 36,
              textAlign: "center",
              boxShadow: "0 24px 60px rgba(0,0,0,0.3)",
            }}
          >
            <div
              style={{
                width: 60,
                height: 60,
                background: "#fef2f2",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 18px",
              }}
            >
              <Icon.Lock size={26} color="#dc2626" />
            </div>
            <h3
              style={{
                margin: "0 0 8px",
                fontSize: 19,
                color: "#1e293b",
                fontWeight: 700,
              }}
            >
              Access Denied
            </h3>
            <p
              style={{
                margin: "0 0 18px",
                fontSize: 14,
                color: "#64748b",
                lineHeight: 1.6,
              }}
            >
              This case is not assigned to you.
              <br />
              You cannot view its details.
            </p>
            <div
              style={{
                background: "#f8fafc",
                borderRadius: 10,
                padding: "10px 16px",
                marginBottom: 22,
                fontSize: 12,
                color: "#475569",
                textAlign: "left",
                border: "1px solid #e2e8f0",
              }}
            >
              <div>
                <strong>Case:</strong>{" "}
                {accessDeniedCase.code || accessDeniedCase.case_id}
              </div>
              <div>
                <strong>Youth:</strong>{" "}
                {accessDeniedCase.youth?.name ||
                  accessDeniedCase.youthName ||
                  "—"}
              </div>
              <div>
                <strong>Assigned to:</strong>{" "}
                {accessDeniedCase.assignedTo ||
                  accessDeniedCase.assigned_to ||
                  "Unassigned"}
              </div>
            </div>
            <button
              onClick={() => setAccessDeniedCase(null)}
              style={{
                background: "linear-gradient(135deg,#0672CB,#0460a9)",
                color: "#fff",
                border: "none",
                borderRadius: 10,
                padding: "11px 32px",
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
                boxShadow: "0 4px 14px rgba(99,102,241,0.35)",
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* ── TO-REVIEW REASON POPUP ── */}
      {showToReviewPopup && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.65)",
            zIndex: 500,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 18,
              width: 460,
              padding: 36,
              boxShadow: "0 24px 60px rgba(0,0,0,0.28)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 14,
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  background: "#fef2f2",
                  borderRadius: 12,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon.AlertTriangle size={20} color="#dc2626" />
              </div>
              <div>
                <div
                  style={{ fontWeight: 700, fontSize: 16, color: "#1e293b" }}
                >
                  Submit for Review
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>
                  This will notify the Admin for case review
                </div>
              </div>
            </div>
            <p
              style={{
                fontSize: 13,
                color: "#475569",
                margin: "0 0 14px",
                lineHeight: 1.6,
              }}
            >
              Please provide a reason why this case needs review. This will be
              audited and visible to the Admin.
            </p>
            <textarea
              value={toReviewReason}
              onChange={(e) => setToReviewReason(e.target.value)}
              placeholder="e.g. Youth requires urgent escalation – risk level has increased significantly..."
              style={{
                width: "100%",
                minHeight: 90,
                padding: "10px 12px",
                borderRadius: 10,
                border: "1.5px solid #e2e8f0",
                fontSize: 13,
                color: "#1e293b",
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box",
                fontFamily: "inherit",
                lineHeight: 1.5,
              }}
            />
            <div
              style={{
                display: "flex",
                gap: 10,
                marginTop: 16,
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={() => {
                  setShowToReviewPopup(false);
                  setToReviewReason("");
                }}
                style={{
                  background: "#f1f5f9",
                  color: "#64748b",
                  border: "none",
                  borderRadius: 10,
                  padding: "9px 22px",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={submitToReview}
                disabled={!toReviewReason.trim() || workStatusSaving}
                style={{
                  background: toReviewReason.trim()
                    ? "linear-gradient(135deg,#dc2626,#ef4444)"
                    : "#e2e8f0",
                  color: toReviewReason.trim() ? "#fff" : "#94a3b8",
                  border: "none",
                  borderRadius: 10,
                  padding: "9px 24px",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: toReviewReason.trim() ? "pointer" : "not-allowed",
                }}
              >
                {workStatusSaving ? "Submitting…" : "Submit for Review"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── REASSIGNMENT REQUEST POPUP ── */}
      {showReassignPopup && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.65)",
            zIndex: 500,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 18,
              width: 460,
              padding: 36,
              boxShadow: "0 24px 60px rgba(0,0,0,0.28)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 14,
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  background: "#fffbeb",
                  borderRadius: 12,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon.User size={20} color="#d97706" />
              </div>
              <div>
                <div
                  style={{ fontWeight: 700, fontSize: 16, color: "#1e293b" }}
                >
                  Request Reassignment
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>
                  Route case to Admin for reassignment approval
                </div>
              </div>
            </div>
            <p
              style={{
                fontSize: 13,
                color: "#475569",
                margin: "0 0 14px",
                lineHeight: 1.6,
              }}
            >
              Provide a reason for requesting this case to be reassigned. Admin
              will review and approve or reject your request.
            </p>
            <textarea
              value={reassignReason}
              onChange={(e) => setReassignReason(e.target.value)}
              placeholder="e.g. I am unable to continue due to scheduling conflicts / conflict of interest…"
              style={{
                width: "100%",
                minHeight: 90,
                padding: "10px 12px",
                borderRadius: 10,
                border: "1.5px solid #e2e8f0",
                fontSize: 13,
                color: "#1e293b",
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box",
                fontFamily: "inherit",
                lineHeight: 1.5,
              }}
            />
            <div
              style={{
                display: "flex",
                gap: 10,
                marginTop: 16,
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={() => {
                  setShowReassignPopup(false);
                  setReassignReason("");
                }}
                style={{
                  background: "#f1f5f9",
                  color: "#64748b",
                  border: "none",
                  borderRadius: 10,
                  padding: "9px 22px",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={submitReassignRequest}
                disabled={!reassignReason.trim() || reassignSaving}
                style={{
                  background: reassignReason.trim()
                    ? "linear-gradient(135deg,#d97706,#f59e0b)"
                    : "#e2e8f0",
                  color: reassignReason.trim() ? "#fff" : "#94a3b8",
                  border: "none",
                  borderRadius: 10,
                  padding: "9px 24px",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: reassignReason.trim() ? "pointer" : "not-allowed",
                }}
              >
                {reassignSaving ? "Submitting…" : "Request Reassignment"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── ONBOARDING WELCOME MODAL ── */}
      {onboardingActive && !onboardingDone && onboardingStep === 0 && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.7)",
            zIndex: 200,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 20,
              maxWidth: 520,
              width: "90%",
              padding: 40,
              textAlign: "center",
              boxShadow: "0 24px 60px rgba(0,0,0,0.3)",
            }}
          >
            <h2 style={{ margin: "0 0 8px", fontSize: 22, color: "#1e293b" }}>
              Welcome to the SCS Youth Helper Dashboard
            </h2>
            <p
              style={{
                margin: "0 0 8px",
                color: "#64748b",
                fontSize: 14,
                lineHeight: 1.6,
              }}
            >
              This short walkthrough will guide you through every feature — from
              viewing cases to using the recommendation chatbot.
            </p>
            <p
              style={{
                margin: "0 0 24px",
                color: "#0672CB",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              AI assists prioritisation and guidance. All outreach decisions are
              yours.
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button
                onClick={() => setOnboardingStep(1)}
                style={{
                  background: "linear-gradient(135deg, #0672CB, #0460a9)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 10,
                  padding: "11px 32px",
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: "pointer",
                  boxShadow: "0 4px 14px rgba(99,102,241,0.4)",
                }}
              >
                Start Walkthrough
              </button>
              <button
                onClick={() => {
                  setOnboardingActive(false);
                  setOnboardingDone(true);
                }}
                style={{
                  background: "#f1f5f9",
                  color: "#64748b",
                  border: "none",
                  borderRadius: 10,
                  padding: "11px 22px",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                Skip for now
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── ONBOARDING STEP OVERLAY ── */}
      {onboardingActive && !onboardingDone && onboardingStep >= 1 && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.55)",
            zIndex: 200,
            pointerEvents: "none",
          }}
        ></div>
      )}
      {onboardingActive &&
        !onboardingDone &&
        onboardingStep >= 1 &&
        (() => {
          const step = ONBOARDING_STEPS[onboardingStep];
          if (!step) return null;
          const posMap = {
            "tab-all": { top: 160, left: "50%", transform: "translateX(-50%)" },
            "risk-badge": {
              top: 200,
              right: 20,
              left: "auto",
              transform: "none",
            },
            "status-badge": {
              top: 200,
              right: 20,
              left: "auto",
              transform: "none",
            },
            "tab-assigned": {
              top: 160,
              left: "50%",
              transform: "translateX(-50%)",
            },
            "workspace-panel": { top: 240, left: "calc(50% - 160px)" },
            "youth-profile": {
              top: 180,
              right: 20,
              left: "auto",
              transform: "none",
            },
            "reach-out-button": {
              top: 240,
              right: 20,
              left: "auto",
              transform: "none",
            },
            "case-detail-area": {
              top: 240,
              right: 20,
              left: "auto",
              transform: "none",
            },
            "checklist-panel": {
              top: 380,
              right: 20,
              left: "auto",
              transform: "none",
            },
            "chatbot-area": {
              bottom: 100,
              right: 20,
              left: "auto",
              top: "auto",
              transform: "none",
            },
          };
          const pos = posMap[step.target] || {
            top: 200,
            left: "50%",
            transform: "translateX(-50%)",
          };
          return (
            <div
              style={{
                position: "fixed",
                ...pos,
                zIndex: 201,
                pointerEvents: "auto",
                width: 380,
                background: "#fff",
                borderRadius: 16,
                boxShadow: "0 16px 48px rgba(0,0,0,0.28)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  background: "linear-gradient(135deg, #0672CB, #0460a9)",
                  padding: "14px 20px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ color: "#fff", fontSize: 13, fontWeight: 600 }}>
                  Step {step.step} of {step.total}
                </span>
                <button
                  onClick={() => {
                    setOnboardingActive(false);
                    setOnboardingDone(true);
                  }}
                  style={{
                    background: "rgba(255,255,255,0.2)",
                    border: "none",
                    color: "#fff",
                    borderRadius: 6,
                    width: 24,
                    height: 24,
                    cursor: "pointer",
                    fontSize: 14,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Icon.X size={14} />
                </button>
              </div>
              <div style={{ padding: "18px 20px 20px" }}>
                <div style={{ marginBottom: 10 }}>
                  <h3
                    style={{
                      margin: 0,
                      fontSize: 15,
                      color: "#1e293b",
                      lineHeight: 1.3,
                    }}
                  >
                    {step.title}
                  </h3>
                </div>
                <p
                  style={{
                    margin: "0 0 16px",
                    fontSize: 13,
                    color: "#64748b",
                    lineHeight: 1.55,
                  }}
                >
                  {step.desc}
                </p>
                {/* Visual example box */}
                <div
                  style={{
                    background: "#f8fafc",
                    border: "1px dashed #cbd5e1",
                    borderRadius: 10,
                    padding: "10px 14px",
                    marginBottom: 16,
                  }}
                >
                  <div
                    style={{
                      fontSize: 10,
                      color: "#94a3b8",
                      textTransform: "uppercase",
                      letterSpacing: "0.8px",
                      marginBottom: 4,
                    }}
                  >
                    Look for:
                  </div>
                  <div style={{ fontSize: 12, color: "#475569" }}>
                    {step.step === 1 &&
                      "The dashboard header and privacy banner at the top."}
                    {step.step === 2 &&
                      "Cases organized into category columns (Self-Harm, Bullying, etc.), with highest priority cases at the top of each column. Risk badges (green to red) and the data freshness indicator top-right."}
                    {step.step === 3 &&
                      "The highlighted RISK BADGE showing the color-coded risk level (1-5). Notice how Critical (5) is red, Medium (3) is yellow, and Low (1) is green."}
                    {step.step === 4 &&
                      "The highlighted STATUS BADGE next to the risk level. Active = blue, Escalated = red, Monitoring = gray, Pending = yellow."}
                    {step.step === 5 &&
                      "The 'Assigned to Me' tab — cases here show a 'MINE' badge in All Cases view."}
                    {step.step === 6 &&
                      "Your assigned case cards in the left panel. Click one to open it."}
                    {step.step === 7 &&
                      "Grab any case card and drag it up or down to reorder. Your custom order will be saved."}
                    {step.step === 8 &&
                      "The highlighted YOUTH PROFILE card showing the person's avatar, name, age, and Instagram handle. This is who you'll be supporting."}
                    {step.step === 9 &&
                      "The highlighted 'REACH OUT VIA INSTAGRAM' button. Click this when ready to initiate contact. Always review protocols first!"}
                    {step.step === 10 &&
                      "The AI signals section explaining why this case was flagged. Each numbered signal shows specific patterns detected."}
                    {step.step === 11 &&
                      "The checklist with mandatory items and the + button to add custom items and comments."}
                  </div>
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 10,
                    justifyContent: "flex-end",
                  }}
                >
                  {onboardingStep > 1 && (
                    <button
                      onClick={() => setOnboardingStep((s) => s - 1)}
                      style={{
                        background: "#f1f5f9",
                        color: "#64748b",
                        border: "none",
                        borderRadius: 8,
                        padding: "8px 18px",
                        fontSize: 13,
                        cursor: "pointer",
                      }}
                    >
                      Back
                    </button>
                  )}
                  {onboardingStep < 11 ? (
                    <button
                      onClick={() => setOnboardingStep((s) => s + 1)}
                      style={{
                        background: "linear-gradient(135deg, #0672CB, #0460a9)",
                        color: "#fff",
                        border: "none",
                        borderRadius: 8,
                        padding: "8px 22px",
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Next
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        setOnboardingActive(false);
                        setOnboardingDone(true);
                      }}
                      style={{
                        background: "linear-gradient(135deg, #10b981, #059669)",
                        color: "#fff",
                        border: "none",
                        borderRadius: 8,
                        padding: "8px 22px",
                        fontSize: 13,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Done
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })()}

      {/* ── MAIN BODY ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Loading State */}
        {loading && (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "#fff",
            }}
          >
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>⏳</div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: "#1e293b",
                  marginBottom: 8,
                }}
              >
                Loading cases from database...
              </div>
              <div style={{ fontSize: 13, color: "#94a3b8" }}>
                Connecting to MongoDB
              </div>
            </div>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "#fff",
            }}
          >
            <div style={{ textAlign: "center", maxWidth: 400 }}>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: "#dc2626",
                  marginBottom: 8,
                }}
              >
                Failed to load cases
              </div>
              <div style={{ fontSize: 13, color: "#64748b", marginBottom: 20 }}>
                {error}
              </div>
              <button
                onClick={() => window.location.reload()}
                style={{
                  background: "linear-gradient(135deg, #0672CB, #0460a9)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 10,
                  padding: "10px 24px",
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Main Content - only show when not loading and no error */}
        {!loading && !error && (
          <div
            id="workspace-panel"
            style={{
              flex: selectedCase ? "0 0 50%" : 1,
              minWidth: selectedCase ? 480 : undefined,
              background: "rgba(255,255,255,0.97)",
              borderRadius: 16,
              margin: 20,
              marginRight: selectedCase ? 12 : 20,
              boxShadow: "0 2px 16px rgba(0,0,0,0.06)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              transition: "all 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
            }}
          >
            {/* Tabs */}
            <div
              id="tab-all"
              style={{
                display: "flex",
                background:
                  highlightTarget === "tab-all" ||
                  highlightTarget === "tab-assigned"
                    ? "#eef2ff"
                    : "#fff",
                transition: "background 0.3s",
                border:
                  highlightTarget === "tab-all" ||
                  highlightTarget === "tab-assigned"
                    ? "2px solid #0672CB"
                    : "none",
                borderBottom: "1px solid #e2e8f0",
                borderRadius: "0 0 0 0",
              }}
            >
              <button
                onClick={() => {
                  setActiveTab("all");
                  setSelectedCase(null);
                }}
                style={{
                  flex: 1,
                  padding: "13px 0",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontSize: 13,
                  fontWeight: activeTab === "all" ? 700 : 500,
                  color: activeTab === "all" ? "#0672CB" : "#64748b",
                  borderBottom:
                    activeTab === "all"
                      ? "3px solid #0672CB"
                      : "3px solid transparent",
                  transition: "all 0.2s",
                }}
              >
                <Icon.List
                  size={13}
                  color={activeTab === "all" ? "#0672CB" : "#94a3b8"}
                  style={{
                    display: "inline",
                    verticalAlign: "middle",
                    marginRight: 6,
                  }}
                />
                All Cases{" "}
                <span
                  style={{
                    background: "#e0e7ff",
                    color: "#4338ca",
                    borderRadius: 10,
                    padding: "1px 8px",
                    fontSize: 11,
                    marginLeft: 4,
                  }}
                >
                  {cases.length}
                </span>
              </button>
              <button
                id="tab-assigned"
                onClick={() => {
                  setActiveTab("assigned");
                  setSelectedCase(null);
                }}
                style={{
                  flex: 1,
                  padding: "13px 0",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontSize: 13,
                  fontWeight: activeTab === "assigned" ? 700 : 500,
                  color: activeTab === "assigned" ? "#0672CB" : "#64748b",
                  borderBottom:
                    activeTab === "assigned"
                      ? "3px solid #0672CB"
                      : "3px solid transparent",
                  transition: "all 0.2s",
                }}
              >
                <Icon.User
                  size={13}
                  color={activeTab === "assigned" ? "#0672CB" : "#94a3b8"}
                  style={{
                    display: "inline",
                    verticalAlign: "middle",
                    marginRight: 6,
                  }}
                />
                Assigned to Me{" "}
                <span
                  style={{
                    background: "#ddd6fe",
                    color: "#5b21b6",
                    borderRadius: 10,
                    padding: "1px 8px",
                    fontSize: 11,
                    marginLeft: 4,
                  }}
                >
                  {myAssignedCases.length}
                </span>
              </button>
              {currentUser.role === "Admin" && (
                <button
                  onClick={() => {
                    setActiveTab("review");
                    setSelectedCase(null);
                  }}
                  style={{
                    flex: 1,
                    padding: "13px 0",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    fontSize: 13,
                    fontWeight: activeTab === "review" ? 700 : 500,
                    color: activeTab === "review" ? "#dc2626" : "#64748b",
                    borderBottom:
                      activeTab === "review"
                        ? "3px solid #dc2626"
                        : "3px solid transparent",
                    transition: "all 0.2s",
                  }}
                >
                  <Icon.AlertTriangle
                    size={13}
                    color={activeTab === "review" ? "#dc2626" : "#94a3b8"}
                    style={{
                      display: "inline",
                      verticalAlign: "middle",
                      marginRight: 6,
                    }}
                  />
                  Needs Review{" "}
                  {needsReviewCases.length > 0 && (
                    <span
                      style={{
                        background: "#fee2e2",
                        color: "#991b1b",
                        borderRadius: 10,
                        padding: "1px 8px",
                        fontSize: 11,
                        marginLeft: 4,
                      }}
                    >
                      {needsReviewCases.length}
                    </span>
                  )}
                </button>
              )}
            </div>
            {/* Case list */}
            {activeTab === "all" ? (
              <div style={{ flex: 1, display: "flex", padding: 24, gap: 24, overflow: "hidden" }}>
                <div style={{ width: 280, flexShrink: 0, overflowY: "auto" }}>
                  <YouthHelperCard user={currentUser} stats={stats} />
                </div>

                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20, overflow: "auto" }}>
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

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
                    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: T.navyMid }}>Risk Distribution</div>
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

                    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: T.navyMid }}>Weekly Risk Trend</div>
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

                    <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 20, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: T.navyMid }}>By Platform</div>
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

                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: T.navyMid, marginBottom: 14 }}>All Active Cases ({cases.length})</div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
                      {cases.map((c) => (
                        <CasePanelCard key={c.id} c={{ ...c, risk: c.risk || riskLevelToLabel(c.riskLevel || 3), user: c.user || c.user_id || c.youth?.handle }} onClick={openCase} isSelected={false} />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : activeTab === "assigned" ? (
              <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
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
                  {!selectedCase && (
                    <div style={{ padding: 20, overflowY: "auto" }}>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
                        {[
                          { label: "My Cases", value: stats.assignedToMe, color: T.indigo, bg: "#eff6ff", icon: "📋" },
                          { label: "Critical", value: stats.myCritical, color: T.danger, bg: "#fef2f2", icon: "🚨" },
                          { label: "High", value: stats.myHigh, color: "#ea580c", bg: "#fff7ed", icon: "⚠️" },
                          { label: "Med/Low", value: stats.myOther, color: T.success, bg: "#f0fdf4", icon: "✅" },
                        ].map((s, i) => (
                          <div
                            key={i}
                            style={{
                              background: "#fff",
                              border: "1px solid #e2e8f0",
                              borderRadius: 14,
                              padding: "16px 18px",
                              position: "relative",
                              overflow: "hidden",
                              boxShadow: "0 2px 8px rgba(0,0,0,0.03)",
                            }}
                          >
                            <div style={{ position: "absolute", top: 0, left: 0, width: 4, height: "100%", background: s.color }} />
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                              <div>
                                <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>{s.label}</div>
                                <div style={{ fontSize: 28, fontWeight: 800, color: s.color }}>{s.value}</div>
                              </div>
                              <div style={{ fontSize: 24, background: s.bg, padding: "8px", borderRadius: 8 }}>{s.icon}</div>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 20 }}>
                        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 18, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 14, color: T.navyMid }}>My Risk Distribution</div>
                          <ResponsiveContainer width="100%" height={140}>
                            <PieChart>
                              <Pie data={chartData.myRiskData} cx="50%" cy="50%" innerRadius={35} outerRadius={55} paddingAngle={3} dataKey="value">
                                {chartData.myRiskData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                              </Pie>
                              <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 11 }} />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>

                        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 18, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 14, color: T.navyMid }}>Work Status</div>
                          <ResponsiveContainer width="100%" height={140}>
                            <PieChart>
                              <Pie data={chartData.myWorkStatusData} cx="50%" cy="50%" innerRadius={35} outerRadius={55} paddingAngle={3} dataKey="value">
                                {chartData.myWorkStatusData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                              </Pie>
                              <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 11 }} />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>

                        <div style={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14, padding: 18, boxShadow: "0 2px 8px rgba(0,0,0,0.03)" }}>
                          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 14, color: T.navyMid }}>By Category</div>
                          <ResponsiveContainer width="100%" height={140}>
                            <BarChart data={chartData.myCategoryData} layout="vertical">
                              <XAxis type="number" tick={{ fontSize: 9, fill: T.muted }} axisLine={false} tickLine={false} />
                              <YAxis type="category" dataKey="category" tick={{ fontSize: 10, fill: T.slate }} axisLine={false} tickLine={false} width={80} />
                              <Tooltip contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 11 }} />
                              <Bar dataKey="cases" fill={T.indigo} radius={[0, 6, 6, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      <div style={{ fontSize: 14, fontWeight: 700, color: T.navyMid, marginBottom: 14, display: "flex", alignItems: "center", gap: 8 }}>
                        <Icon.User size={16} color={T.indigo} /> My Assigned Cases ({myAssignedCases.length})
                      </div>
                    </div>
                  )}

                  <div style={{ flex: 1, overflowY: "auto", padding: selectedCase ? 20 : "0 20px 20px 20px" }}>
                    {myAssignedCases.length === 0 ? (
                      <div style={{ textAlign: "center", padding: 60, color: T.muted }}>
                        <Icon.User size={40} color="#e2e8f0" />
                        <div style={{ fontSize: 16, fontWeight: 600, marginTop: 16, color: T.slate }}>No cases assigned to you yet</div>
                        <div style={{ fontSize: 13, marginTop: 6 }}>Cases will appear here when assigned by your supervisor.</div>
                      </div>
                    ) : (
                      <div style={{ display: "grid", gridTemplateColumns: selectedCase ? "1fr" : "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
                        {myAssignedCases.map((c, index) => (
                          <div
                            key={c.id}
                            draggable
                            onDragStart={(e) => handleDragStart(index, e)}
                            onDragOver={(e) => handleDragOver(e, index)}
                            onDragEnd={handleDragEnd}
                            style={{ cursor: isDragging ? "move" : "pointer", opacity: draggedIndex === index ? 0.5 : 1, transition: "opacity 0.2s" }}
                          >
                            <CasePanelCard c={{ ...c, risk: c.risk || riskLevelToLabel(c.riskLevel || 3), user: c.user || c.user_id || c.youth?.handle }} onClick={handleCaseClick} isSelected={selectedCase?.id === c.id} />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              // Needs Review list (admin only)
              <div
                style={{
                  flex: 1,
                  overflowY: "auto",
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 16,
                }}
              >
                {needsReviewCases.length === 0 ? (
                  <div
                    style={{
                      textAlign: "center",
                      marginTop: 40,
                      color: "#94a3b8",
                    }}
                  >
                    <div style={{ fontSize: 14, fontWeight: 600 }}>
                      No cases need review
                    </div>
                  </div>
                ) : (
                  needsReviewCases.map((c) => (
                    <CaseCard
                      key={c.id}
                      c={c}
                      isAssignedView={false}
                      highlight={false}
                      onClick={(c) => setSelectedCase(c)}
                      llmSummary={llmSummaries[c.case_user || c.user_id]}
                      onViewSummary={handleViewSummary}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        )}

        {/* ── RIGHT: CASE DETAIL SIDE PANEL ── */}
        {selectedCase && !loading && !error && (
          <div
            id="case-detail-area"
            style={{
              flex: "0 0 48%",
              maxWidth: 640,
              minWidth: 420,
              background: "#fff",
              borderLeft: "1px solid #e5e7eb",
              borderRadius: 16,
              margin: "20px 20px 20px 0",
              boxShadow:
                "-8px 0 32px rgba(0,0,0,0.08), 0 2px 16px rgba(0,0,0,0.04)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              transition: "all 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
            }}
          >
            {/* Scrollable Content */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {/* Case header */}
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
                      fontSize: 18,
                      color: "#fff",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      transition: "background 0.2s",
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background =
                        "rgba(255,255,255,0.25)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background =
                        "rgba(255,255,255,0.15)")
                    }
                  >
                    <Icon.ArrowLeft size={18} />
                  </button>
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 700,
                          fontSize: 16,
                          color: "#fff",
                          letterSpacing: "0.3px",
                        }}
                      >
                        {selectedCase.code}
                      </span>
                      <RiskBadge
                        level={selectedCase.riskLevel}
                        score={selectedCase.current_risk_score}
                      />
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "rgba(255,255,255,0.75)",
                        marginTop: 3,
                      }}
                    >
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
                    transition: "background 0.2s",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background =
                      "rgba(255,255,255,0.25)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background =
                      "rgba(255,255,255,0.15)")
                  }
                >
                  <Icon.X size={14} /> Close
                </button>
              </div>

              {/* Work Status + Case Status bar */}
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
                  <span
                    style={{
                      fontSize: 10,
                      color: "#94a3b8",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                    }}
                  >
                    Status
                  </span>
                  <CaseStatusBadge
                    caseStatus={
                      selectedCase.case_status ||
                      (selectedCase.assignedToMe ? "assigned" : "unassigned")
                    }
                  />
                </div>
                <div
                  style={{ width: 1, height: 16, background: "#e2e8f0" }}
                ></div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      fontSize: 10,
                      color: "#94a3b8",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                    }}
                  >
                    Work
                  </span>
                  <WorkStatusBadge
                    workStatus={
                      workStatus || selectedCase.work_status || "not_started"
                    }
                  />
                  <select
                    value={
                      workStatus || selectedCase.work_status || "not_started"
                    }
                    onChange={(e) => handleWorkStatusChange(e.target.value)}
                    disabled={workStatusSaving}
                    style={{
                      fontSize: 11,
                      padding: "4px 8px",
                      borderRadius: 6,
                      border: "1px solid #e2e8f0",
                      background: "#fff",
                      color: "#475569",
                      cursor: "pointer",
                      fontWeight: 500,
                    }}
                  >
                    <option value="not_started">Not Started</option>
                    <option value="in_progress">In Progress</option>
                    <option value="to_review">To Review</option>
                    <option value="completed">Completed</option>
                  </select>
                  {workStatusSaving && (
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>
                      Saving…
                    </span>
                  )}
                </div>
                {reassignMsg && (
                  <div
                    style={{
                      marginLeft: "auto",
                      fontSize: 11,
                      color: "#065f46",
                      background: "#d1fae5",
                      borderRadius: 8,
                      padding: "4px 12px",
                      border: "1px solid #6ee7b7",
                    }}
                  >
                    {reassignMsg}
                  </div>
                )}
              </div>

              {/* Detail-view tab row */}
              <div
                style={{
                  display: "flex",
                  gap: 0,
                  borderBottom: "1px solid #f1f5f9",
                  background: "#fff",
                  flexShrink: 0,
                  paddingLeft: 8,
                }}
              >
                {[
                  { id: "overview", label: "Overview" },
                  { id: "timeline", label: "Timeline" },
                  { id: "reassign", label: "Reassign" },
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
                      borderBottom:
                        detailTab === t.id
                          ? "2px solid #3b82f6"
                          : "2px solid transparent",
                      cursor: "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Detail content */}
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  overflowY: "auto",
                  background: "#f8fafc",
                }}
              >
                {detailTab === "overview" && (
                  <div
                    style={{
                      padding: "24px 28px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 20,
                    }}
                  >
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
                      <Icon.Shield
                        size={16}
                        style={{
                          flexShrink: 0,
                          color: "#0284c7",
                          marginTop: 1,
                        }}
                      />
                      <div
                        style={{
                          fontSize: 12,
                          color: "#0369a1",
                          lineHeight: 1.5,
                        }}
                      >
                        <strong>Privacy:</strong> AI-generated risk signals
                        only. No raw social media posts or personal content is
                        stored.
                      </div>
                    </div>

                    {/* Review Pending Card - Show when review is pending */}
                    {selectedCase.review_requests &&
                      selectedCase.review_requests.length > 0 &&
                      (() => {
                        const latestReview =
                          selectedCase.review_requests[
                            selectedCase.review_requests.length - 1
                          ];
                        const isPending =
                          latestReview.request_status === "pending";

                        if (isPending) {
                          return (
                            <div
                              style={{
                                background: "#fff",
                                borderRadius: 12,
                                border: "1.5px solid #fbbf24",
                                padding: 20,
                              }}
                            >
                              <div
                                style={{
                                  fontWeight: 600,
                                  fontSize: 13,
                                  marginBottom: 12,
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 6,
                                }}
                              >
                                <Icon.Clock size={14} />
                                Review Pending
                                <span
                                  style={{
                                    marginLeft: "auto",
                                    fontSize: 11,
                                    fontWeight: 600,
                                    color: "#d97706",
                                    background: "#fffbeb",
                                    padding: "4px 10px",
                                    borderRadius: 6,
                                  }}
                                >
                                  ⏳ Awaiting Admin
                                </span>
                              </div>

                              <div
                                style={{
                                  fontSize: 10,
                                  color: "#94a3b8",
                                  textTransform: "uppercase",
                                  letterSpacing: "0.5px",
                                  marginBottom: 4,
                                }}
                              >
                                Your Review Request
                              </div>
                              <div
                                style={{
                                  fontSize: 13,
                                  color: "#475569",
                                  lineHeight: 1.5,
                                  background: "#fffbeb",
                                  padding: "10px 12px",
                                  borderRadius: 8,
                                  border: "1px solid #fde68a",
                                }}
                              >
                                {latestReview.reason || "No reason provided"}
                              </div>
                              <div
                                style={{
                                  fontSize: 11,
                                  color: "#94a3b8",
                                  marginTop: 4,
                                }}
                              >
                                Submitted{" "}
                                {latestReview.created_at
                                  ? new Date(
                                      latestReview.created_at,
                                    ).toLocaleString("en-US", {
                                      month: "short",
                                      day: "numeric",
                                      year: "numeric",
                                      hour: "numeric",
                                      minute: "2-digit",
                                    })
                                  : "—"}
                              </div>
                            </div>
                          );
                        }

                        return null;
                      })()}

                    {/* Admin Resolution Card - Only show if admin has responded */}
                    {selectedCase.review_requests &&
                      selectedCase.review_requests.length > 0 &&
                      (() => {
                        const latestReview =
                          selectedCase.review_requests[
                            selectedCase.review_requests.length - 1
                          ];
                        const isResolved =
                          latestReview.request_status === "resolved";

                        if (isResolved && latestReview.resolution_notes) {
                          // Parse approach and comments from resolution_notes
                          const resolutionText =
                            latestReview.resolution_notes || "";
                          const approachMatch = resolutionText.match(
                            /\*\*Approach:\*\*\s*([\s\S]*?)(?=\*\*Comments:\*\*|$)/,
                          );
                          const commentsMatch = resolutionText.match(
                            /\*\*Comments:\*\*\s*([\s\S]*)/,
                          );

                          const approach = approachMatch
                            ? approachMatch[1].trim()
                            : null;
                          const comments = commentsMatch
                            ? commentsMatch[1].trim()
                            : approach
                              ? null
                              : resolutionText;

                          return (
                            <div
                              style={{
                                background: "#fff",
                                borderRadius: 12,
                                border: "1.5px solid #10b981",
                                padding: 20,
                              }}
                            >
                              <div
                                style={{
                                  fontWeight: 600,
                                  fontSize: 13,
                                  marginBottom: 12,
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 6,
                                }}
                              >
                                <Icon.CheckCircle size={14} color="#10b981" />
                                Admin Response
                                <span
                                  style={{
                                    marginLeft: "auto",
                                    fontSize: 11,
                                    fontWeight: 600,
                                    color: "#065f46",
                                    background: "#d1fae5",
                                    padding: "4px 10px",
                                    borderRadius: 6,
                                  }}
                                >
                                  ✓ Resolved
                                </span>
                              </div>

                              <div
                                style={{
                                  fontSize: 10,
                                  color: "#94a3b8",
                                  textTransform: "uppercase",
                                  letterSpacing: "0.5px",
                                  marginBottom: 4,
                                }}
                              >
                                Your Original Request
                              </div>
                              <div
                                style={{
                                  fontSize: 12,
                                  color: "#64748b",
                                  lineHeight: 1.5,
                                  background: "#f8fafc",
                                  padding: "8px 10px",
                                  borderRadius: 6,
                                  border: "1px solid #e2e8f0",
                                  marginBottom: 12,
                                  fontStyle: "italic",
                                }}
                              >
                                "{latestReview.reason || "No reason provided"}"
                              </div>

                              {approach && (
                                <>
                                  <div
                                    style={{
                                      fontSize: 10,
                                      color: "#065f46",
                                      textTransform: "uppercase",
                                      letterSpacing: "0.5px",
                                      marginBottom: 4,
                                      fontWeight: 600,
                                    }}
                                  >
                                    Recommended Approach
                                  </div>
                                  <div
                                    style={{
                                      fontSize: 13,
                                      color: "#065f46",
                                      lineHeight: 1.6,
                                      background: "#d1fae5",
                                      padding: "12px 14px",
                                      borderRadius: 8,
                                      border: "1px solid #6ee7b7",
                                      fontWeight: 500,
                                      marginBottom: 12,
                                    }}
                                  >
                                    {approach}
                                  </div>
                                </>
                              )}

                              {comments && (
                                <>
                                  <div
                                    style={{
                                      fontSize: 10,
                                      color: "#065f46",
                                      textTransform: "uppercase",
                                      letterSpacing: "0.5px",
                                      marginBottom: 4,
                                      fontWeight: 600,
                                    }}
                                  >
                                    Additional Comments
                                  </div>
                                  <div
                                    style={{
                                      fontSize: 13,
                                      color: "#065f46",
                                      lineHeight: 1.6,
                                      background: "#d1fae5",
                                      padding: "12px 14px",
                                      borderRadius: 8,
                                      border: "1px solid #6ee7b7",
                                      fontWeight: 500,
                                    }}
                                  >
                                    {comments}
                                  </div>
                                </>
                              )}

                              <div
                                style={{
                                  fontSize: 11,
                                  color: "#94a3b8",
                                  marginTop: 8,
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 4,
                                }}
                              >
                                <Icon.User size={10} />
                                <span>
                                  Reviewed by Admin ·{" "}
                                  {latestReview.resolved_at
                                    ? new Date(
                                        latestReview.resolved_at,
                                      ).toLocaleString("en-US", {
                                        month: "short",
                                        day: "numeric",
                                        year: "numeric",
                                        hour: "numeric",
                                        minute: "2-digit",
                                      })
                                    : "—"}
                                </span>
                              </div>
                            </div>
                          );
                        }

                        return null;
                      })()}

                    {/* Youth Profile Card */}
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 12,
                        border: "1px solid #e2e8f0",
                        padding: 20,
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: 14,
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          color: "#1e293b",
                          borderBottom: "1px solid #f1f5f9",
                          paddingBottom: 12,
                        }}
                      >
                        <Icon.User size={16} color="#3b82f6" /> Youth Profile
                      </div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 14,
                          marginBottom: 14,
                        }}
                      >
                        <div
                          style={{
                            fontSize: 48,
                            width: 64,
                            height: 64,
                            background:
                              "linear-gradient(135deg, #ddd6fe, #e0e7ff)",
                            borderRadius: "50%",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          {selectedCase.youth?.avatar ?? "U"}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div
                            style={{
                              fontSize: 16,
                              fontWeight: 700,
                              color: "#1e293b",
                              marginBottom: 2,
                            }}
                          >
                            {selectedCase.youth?.name ?? "—"}
                          </div>
                          <div
                            style={{
                              fontSize: 13,
                              color: "#64748b",
                              marginBottom: 4,
                            }}
                          >
                            Age: {selectedCase.youth?.age ?? "—"} · Instagram:{" "}
                            {selectedCase.youth?.handle ?? "—"}
                          </div>
                          <button
                            onClick={() =>
                              window.open(
                                selectedCase.youth?.instagramUrl ?? "#",
                                "_blank",
                              )
                            }
                            style={{
                              background:
                                "linear-gradient(135deg, #0672CB, #0460a9)",
                              color: "#fff",
                              border: "none",
                              borderRadius: 8,
                              padding: "6px 14px",
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: "pointer",
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              marginTop: 6,
                            }}
                            onMouseEnter={(e) =>
                              (e.currentTarget.style.opacity = "0.9")
                            }
                            onMouseLeave={(e) =>
                              (e.currentTarget.style.opacity = "1")
                            }
                          >
                            <Icon.Send size={12} /> Reach Out via Instagram
                          </button>
                        </div>
                      </div>
                      <div
                        style={{
                          background: "#fef3c7",
                          border: "1px solid #fbbf24",
                          borderRadius: 8,
                          padding: "8px 12px",
                          fontSize: 11,
                          color: "#92400e",
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 8,
                        }}
                      >
                        <Icon.AlertTriangle
                          size={14}
                          style={{ flexShrink: 0 }}
                        />
                        <div>
                          <strong>Important:</strong> Always use trauma-informed
                          communication. Review SCS outreach protocols before
                          initiating contact.
                        </div>
                      </div>
                    </div>

                    {/* Risk Assessment */}
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 12,
                        border: "1px solid #e2e8f0",
                        padding: 20,
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: 14,
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          color: "#1e293b",
                          borderBottom: "1px solid #f1f5f9",
                          paddingBottom: 12,
                        }}
                      >
                        <Icon.TrendingUp size={16} color="#dc2626" /> Risk
                        Assessment
                      </div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 16,
                        }}
                      >
                        <span
                          style={{
                            fontSize: 32,
                            fontWeight: 800,
                            color: (
                              RISK_COLORS[selectedCase.riskLevel] ||
                              RISK_COLORS[3]
                            ).text,
                          }}
                        >
                          {selectedCase.current_risk_score?.toFixed(1) ?? "—"}
                          <span
                            style={{
                              fontSize: 18,
                              fontWeight: 400,
                              color: "#94a3b8",
                            }}
                          >
                            %
                          </span>
                        </span>
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "#94a3b8",
                          marginTop: 6,
                        }}
                      >
                        {
                          (
                            RISK_COLORS[selectedCase.riskLevel] ||
                            RISK_COLORS[3]
                          ).label
                        }{" "}
                        risk · Category: {selectedCase.category}
                      </div>
                    </div>

                    {/* AI Explanation Signals */}
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 12,
                        border: "1px solid #e2e8f0",
                        padding: 20,
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: 14,
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          color: "#1e293b",
                          borderBottom: "1px solid #f1f5f9",
                          paddingBottom: 12,
                        }}
                      >
                        <Icon.Activity size={16} color="#0672CB" /> AI
                        Explanation Signals{" "}
                        <span
                          style={{
                            fontSize: 11,
                            color: "#94a3b8",
                            fontWeight: 400,
                          }}
                        >
                          (why this was flagged)
                        </span>
                      </div>
                      {/* AI Explanation Paragraph */}
                      {selectedCase.ai_explanation_paragraph && (
                        <div
                          style={{
                            background: "#f8fafc",
                            borderLeft: "3px solid #0672CB",
                            padding: "12px 14px",
                            marginBottom: 14,
                            borderRadius: "0 8px 8px 0",
                          }}
                        >
                          <p
                            style={{
                              margin: 0,
                              fontSize: 13,
                              color: "#475569",
                              lineHeight: 1.6,
                            }}
                          >
                            {selectedCase.ai_explanation_paragraph}
                          </p>
                        </div>
                      )}
                      <div
                        style={{
                          fontWeight: 500,
                          fontSize: 12,
                          color: "#64748b",
                          marginBottom: 8,
                        }}
                      >
                        Key Signals Detected:
                      </div>
                      {selectedCase.signals &&
                      selectedCase.signals.length > 0 ? (
                        selectedCase.signals.map((s, i) => (
                          <div
                            key={i}
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 10,
                              padding: "8px 0",
                              borderBottom:
                                i < selectedCase.signals.length - 1
                                  ? "1px solid #f1f5f9"
                                  : "none",
                            }}
                          >
                            <span
                              style={{
                                background: "#eef2ff",
                                color: "#0672CB",
                                borderRadius: 6,
                                width: 22,
                                height: 22,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                fontSize: 11,
                                flexShrink: 0,
                                marginTop: 1,
                              }}
                            >
                              {i + 1}
                            </span>
                            <span
                              style={{
                                fontSize: 13,
                                color: "#475569",
                                lineHeight: 1.5,
                              }}
                            >
                              {s}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div
                          style={{
                            fontSize: 13,
                            color: "#94a3b8",
                            fontStyle: "italic",
                          }}
                        >
                          No signals detected for this case.
                        </div>
                      )}
                    </div>

                    {/* Recommended Actions */}
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 12,
                        border: "1px solid #e2e8f0",
                        padding: 20,
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: 14,
                          marginBottom: 16,
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          color: "#1e293b",
                          borderBottom: "1px solid #f1f5f9",
                          paddingBottom: 12,
                        }}
                      >
                        <Icon.Lightbulb size={16} color="#f59e0b" />
                        Recommended Actions{" "}
                        <span
                          style={{
                            fontSize: 11,
                            color: "#94a3b8",
                            fontWeight: 400,
                          }}
                        >
                          (AI-generated from protocols)
                        </span>
                      </div>

                      {/* Recommended Actions Paragraph */}
                      {selectedCase.recommended_actions_paragraph && (
                        <div
                          style={{
                            background: "#fffbeb",
                            borderLeft: "3px solid #f59e0b",
                            padding: "12px 14px",
                            marginBottom: 14,
                            borderRadius: "0 8px 8px 0",
                          }}
                        >
                          <p
                            style={{
                              margin: 0,
                              fontSize: 13,
                              color: "#475569",
                              lineHeight: 1.6,
                            }}
                          >
                            {selectedCase.recommended_actions_paragraph}
                          </p>
                        </div>
                      )}

                      {loadingRecommendations ? (
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "12px 0",
                            color: "#94a3b8",
                            fontSize: 13,
                          }}
                        >
                          <div
                            style={{
                              width: 16,
                              height: 16,
                              border: "2px solid #e2e8f0",
                              borderTop: "2px solid #0672CB",
                              borderRadius: "50%",
                              animation: "spin 1s linear infinite",
                            }}
                          />
                          Generating recommendations...
                        </div>
                      ) : recommendations.length > 0 ? (
                        <>
                          <div
                            style={{
                              fontWeight: 500,
                              fontSize: 12,
                              color: "#64748b",
                              marginBottom: 8,
                            }}
                          >
                            Suggested Actions:
                          </div>
                          {recommendations.map((rec, i) => (
                            <div
                              key={i}
                              style={{
                                display: "flex",
                                alignItems: "flex-start",
                                gap: 10,
                                padding: "8px 0",
                                borderBottom:
                                  i < recommendations.length - 1
                                    ? "1px solid #f1f5f9"
                                    : "none",
                              }}
                            >
                              <span
                                style={{
                                  background: "#fef3c7",
                                  color: "#92400e",
                                  borderRadius: 6,
                                  width: 22,
                                  height: 22,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  fontSize: 11,
                                  flexShrink: 0,
                                  marginTop: 1,
                                }}
                              >
                                <Icon.Lightbulb size={12} />
                              </span>
                              <span
                                style={{
                                  fontSize: 13,
                                  color: "#475569",
                                  lineHeight: 1.5,
                                }}
                              >
                                {rec}
                              </span>
                            </div>
                          ))}
                        </>
                      ) : (
                        <div
                          style={{
                            fontSize: 13,
                            color: "#94a3b8",
                            fontStyle: "italic",
                          }}
                        >
                          No recommendations available for this case.
                        </div>
                      )}
                    </div>

                    {/* Summary
                <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 18 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Case Summary</div>
                  <p style={{ margin: 0, fontSize: 13, color: "#475569", lineHeight: 1.6 }}>{selectedCase.summary}</p>
                </div> */}

                    {/* Case Checklist - Now inline in vertical flow */}
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 12,
                        border: "1px solid #e2e8f0",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                        overflow: "hidden",
                      }}
                    >
                      <ChecklistPanel
                        caseId={selectedCase.id}
                        highlight={highlightTarget === "checklist-panel"}
                        currentUser={currentUser}
                        inlineMode={true}
                      />
                    </div>
                  </div>
                )}

                {detailTab === "timeline" && (
                  <CaseTimeline
                    caseId={
                      selectedCase.case_id ||
                      selectedCase.code ||
                      selectedCase.id
                    }
                    currentUser={currentUser}
                  />
                )}

                {detailTab === "reassign" && (
                  <div style={{ flex: 1, padding: 28, overflowY: "auto" }}>
                    <div style={{ maxWidth: 520 }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                          marginBottom: 20,
                        }}
                      >
                        <div
                          style={{
                            width: 44,
                            height: 44,
                            background: "#fffbeb",
                            borderRadius: 12,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <Icon.User size={20} color="#d97706" />
                        </div>
                        <div>
                          <div
                            style={{
                              fontWeight: 700,
                              fontSize: 16,
                              color: "#1e293b",
                            }}
                          >
                            Request Reassignment
                          </div>
                          <div style={{ fontSize: 12, color: "#94a3b8" }}>
                            Case: {selectedCase.code || selectedCase.case_id}
                          </div>
                        </div>
                      </div>
                      {selectedCase.case_status === "reassigned" ? (
                        <div
                          style={{
                            background: "#fffbeb",
                            border: "1px solid #fbbf24",
                            borderRadius: 12,
                            padding: 18,
                          }}
                        >
                          <div
                            style={{
                              fontWeight: 600,
                              fontSize: 14,
                              color: "#92400e",
                              marginBottom: 6,
                            }}
                          >
                            ⏳ Reassignment Pending
                          </div>
                          <p
                            style={{
                              margin: 0,
                              fontSize: 13,
                              color: "#78350f",
                              lineHeight: 1.6,
                            }}
                          >
                            A reassignment request for this case is currently
                            pending Admin review. You will be notified once a
                            decision is made.
                          </p>
                        </div>
                      ) : (
                        <>
                          <p
                            style={{
                              fontSize: 13,
                              color: "#475569",
                              marginBottom: 16,
                              lineHeight: 1.6,
                            }}
                          >
                            If you are unable to continue with this case, you
                            can request a reassignment. The Admin will review
                            your request and either approve or reject it.
                          </p>
                          <div style={{ marginBottom: 12 }}>
                            <label
                              style={{
                                display: "block",
                                fontSize: 12,
                                fontWeight: 600,
                                color: "#374151",
                                marginBottom: 6,
                              }}
                            >
                              Reason for Reassignment *
                            </label>
                            <textarea
                              value={reassignReason}
                              onChange={(e) =>
                                setReassignReason(e.target.value)
                              }
                              placeholder="e.g. Conflict of interest, scheduling constraints, etc."
                              style={{
                                width: "100%",
                                minHeight: 100,
                                padding: "10px 12px",
                                borderRadius: 10,
                                border: "1.5px solid #e2e8f0",
                                fontSize: 13,
                                color: "#1e293b",
                                resize: "vertical",
                                outline: "none",
                                boxSizing: "border-box",
                                fontFamily: "inherit",
                                lineHeight: 1.5,
                              }}
                            />
                          </div>
                          <button
                            onClick={submitReassignRequest}
                            disabled={!reassignReason.trim() || reassignSaving}
                            style={{
                              background: reassignReason.trim()
                                ? "linear-gradient(135deg,#d97706,#f59e0b)"
                                : "#e2e8f0",
                              color: reassignReason.trim() ? "#fff" : "#94a3b8",
                              border: "none",
                              borderRadius: 10,
                              padding: "11px 28px",
                              fontSize: 14,
                              fontWeight: 600,
                              cursor: reassignReason.trim()
                                ? "pointer"
                                : "not-allowed",
                            }}
                          >
                            {reassignSaving ? "Submitting…" : "Submit Request"}
                          </button>
                          {reassignMsg && (
                            <div
                              style={{
                                marginTop: 12,
                                fontSize: 12,
                                color: "#065f46",
                                background: "#d1fae5",
                                borderRadius: 8,
                                padding: "8px 14px",
                              }}
                            >
                              {reassignMsg}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── EMPTY STATE ── */}
        {!loading && !error && !selectedCase && activeTab === "assigned" && (
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#94a3b8",
            }}
          >
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 15, fontWeight: 600, color: "#64748b" }}>
                Select a case to view details
              </div>
              <div style={{ fontSize: 13, marginTop: 4 }}>
                Click any card in your assigned list
              </div>
            </div>
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
          background: showChatbot
            ? "#dc2626"
            : "linear-gradient(135deg, #0672CB, #0460a9)",
          border: "none",
          color: "#fff",
          cursor: "pointer",
          fontSize: 22,
          boxShadow: "0 4px 18px rgba(99,102,241,0.45)",
          zIndex: 160,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "all 0.3s",
        }}
        id="chatbot-area"
      >
        {showChatbot ? (
          <Icon.X size={20} color="#fff" />
        ) : (
          <Icon.MessageSquare size={22} color="#fff" />
        )}
      </button>

      {/* ── CHATBOT SLIDE-OUT PANEL ── */}
      <ChatbotPanel
        assignedCases={myAssignedCases}
        highlight={highlightTarget === "chatbot-area"}
        open={showChatbot}
        onClose={() => setShowChatbot(false)}
        selectedCase={selectedCase}
        currentUser={currentUser}
      />

      {/* ── LLM SUMMARY DIALOG ── */}
      <LlmSummaryDialog
        open={summaryDialogOpen}
        onClose={() => setSummaryDialogOpen(false)}
        summary={selectedSummary}
        onGenerate={
          selectedSummary
            ? () => handleGenerateSingleSummary(selectedSummary.case_user)
            : null
        }
      />
    </div>
  );
}

// ─── CHECKLIST PANEL ─────────────────────────────────────────────────
const ITEM_STATUSES = [
  "Not Started",
  "In Progress",
  "Completed",
  "Needs Review",
];
const STATUS_STYLES = {
  "Not Started": { bg: "#f1f5f9", text: "#64748b" },
  "In Progress": { bg: "#dbeafe", text: "#1e40af" },
  Completed: { bg: "#d1fae5", text: "#065f46" },
  "Needs Review": { bg: "#fee2e2", text: "#991b1b" },
};

// ─── CASE TIMELINE ────────────────────────────────────────────────────────────
function CaseTimeline({ caseId, currentUser }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!caseId) return;

    const loadHistory = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await historyAPI.getCaseHistory(caseId);
        // Sort in reverse chronological order (newest first)
        setHistory(data.reverse());
      } catch (err) {
        console.error("Failed to load case history:", err);
        setError(err.message || "Failed to load history");
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, [caseId]);

  const formatDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("en-SG", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const extractSignals = (aiExplanation) => {
    if (!aiExplanation) return [];
    const lines = aiExplanation.split("\n");
    return lines
      .filter(
        (line) => line.trim().startsWith("•") || line.trim().startsWith("-"),
      )
      .map((line) => line.replace(/^[•\-]\s*/, "").trim())
      .filter((line) => line.length > 0);
  };

  const getRiskColor = (score) => {
    if (score >= 90)
      return { bg: "#fee2e2", text: "#991b1b", label: "Critical" };
    if (score >= 75) return { bg: "#ffedd5", text: "#c2410c", label: "High" };
    if (score >= 50) return { bg: "#fef3c7", text: "#92400e", label: "Medium" };
    if (score >= 25)
      return { bg: "#dbeafe", text: "#1e40af", label: "Low-Med" };
    return { bg: "#d1fae5", text: "#065f46", label: "Low" };
  };

  if (loading)
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#94a3b8",
          padding: 40,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>
            Loading case history...
          </div>
        </div>
      </div>
    );

  if (error)
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#94a3b8",
          padding: 40,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#dc2626" }}>
            Failed to load history
          </div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
            {error}
          </div>
        </div>
      </div>
    );

  return (
    <div
      style={{
        flex: 1,
        padding: "24px 20px",
        overflowY: "auto",
        background: "#f8fafc",
      }}
    >
      <div
        style={{
          fontWeight: 700,
          fontSize: 16,
          color: "#1e293b",
          marginBottom: 20,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <Icon.Clock size={18} color="#0672CB" />
        Case History Timeline
        <span
          style={{
            fontSize: 12,
            fontWeight: 500,
            color: "#94a3b8",
            marginLeft: "auto",
          }}
        >
          {history.length} {history.length === 1 ? "entry" : "entries"}
        </span>
      </div>

      {history.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            color: "#94a3b8",
            padding: "60px 20px",
            background: "#fff",
            borderRadius: 12,
            border: "1px solid #e2e8f0",
          }}
        >
          <div
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "#1e293b",
              marginBottom: 12,
            }}
          >
            No History Available
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>
            No history entries yet
          </div>
          <div style={{ fontSize: 12 }}>
            History will appear as the case is updated
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {history.map((entry, index) => {
            const signals = extractSignals(entry.ai_explanation);
            const riskColor = getRiskColor(entry.risk_score);
            const isLatest = index === 0;

            return (
              <div
                key={entry.history_id || index}
                style={{
                  background: "#fff",
                  borderRadius: 12,
                  border: isLatest ? "2px solid #0672CB" : "1px solid #e2e8f0",
                  boxShadow: isLatest
                    ? "0 4px 12px rgba(99,102,241,0.15)"
                    : "0 1px 3px rgba(0,0,0,0.06)",
                  overflow: "hidden",
                }}
              >
                {/* Header with date and risk score */}
                <div
                  style={{
                    background: isLatest
                      ? "linear-gradient(135deg, #0672CB, #0460a9)"
                      : "#f8fafc",
                    padding: "14px 18px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    borderBottom: "1px solid #e2e8f0",
                  }}
                >
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 10 }}
                  >
                    <Icon.Calendar
                      size={16}
                      color={isLatest ? "#fff" : "#0672CB"}
                    />
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: isLatest ? "#fff" : "#1e293b",
                      }}
                    >
                      {formatDate(entry.ingestion_date)}
                    </span>
                    {isLatest && (
                      <span
                        style={{
                          background: "rgba(255,255,255,0.25)",
                          color: "#fff",
                          fontSize: 10,
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: 10,
                        }}
                      >
                        LATEST
                      </span>
                    )}
                  </div>

                  {/* Risk Score Badge */}
                  <div
                    style={{
                      background: isLatest
                        ? "rgba(255,255,255,0.95)"
                        : riskColor.bg,
                      color: riskColor.text,
                      padding: "4px 12px",
                      borderRadius: 20,
                      fontSize: 12,
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <span>{entry.risk_score.toFixed(1)}%</span>
                    <span style={{ fontSize: 10, opacity: 0.7 }}>
                      ({riskColor.label})
                    </span>
                  </div>
                </div>

                {/* Category and Model Version */}
                <div
                  style={{
                    padding: "12px 18px",
                    background: "#fafafa",
                    borderBottom: "1px solid #e2e8f0",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      fontSize: 11,
                      color: "#64748b",
                    }}
                  >
                    <span
                      style={{ display: "flex", alignItems: "center", gap: 4 }}
                    >
                      <strong>Category:</strong> {entry.category}
                    </span>
                    {entry.model_version && (
                      <span
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <strong>Model:</strong> {entry.model_version}
                      </span>
                    )}
                  </div>
                </div>

                {/* AI Signals */}
                {signals.length > 0 && (
                  <div style={{ padding: "16px 18px" }}>
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: "#0672CB",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px",
                        marginBottom: 12,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <Icon.Activity size={12} color="#0672CB" />
                      AI Signals Detected
                    </div>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                      }}
                    >
                      {signals.map((signal, i) => (
                        <div
                          key={i}
                          style={{
                            display: "flex",
                            gap: 10,
                            padding: "10px 12px",
                            background: "#f8fafc",
                            borderLeft: "3px solid #0672CB",
                            borderRadius: "0 8px 8px 0",
                          }}
                        >
                          <span
                            style={{
                              background: "#0672CB",
                              color: "#fff",
                              borderRadius: 6,
                              width: 22,
                              height: 22,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 11,
                              fontWeight: 700,
                              flexShrink: 0,
                            }}
                          >
                            {i + 1}
                          </span>
                          <span
                            style={{
                              fontSize: 12,
                              color: "#475569",
                              lineHeight: 1.6,
                              flex: 1,
                            }}
                          >
                            {signal}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Full explanation (collapsed by default for older entries) */}
                {!isLatest && signals.length === 0 && entry.ai_explanation && (
                  <div
                    style={{
                      padding: "16px 18px",
                      fontSize: 12,
                      color: "#64748b",
                      lineHeight: 1.6,
                      borderTop: "1px solid #f1f5f9",
                    }}
                  >
                    {entry.ai_explanation.substring(0, 200)}...
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ChecklistPanel({
  caseId,
  highlight,
  currentUser,
  inlineMode = false,
}) {
  const displayName = currentUser?.name || "You";
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [comments, setComments] = useState([]);
  const [newItem, setNewItem] = useState("");
  const [newComment, setNewComment] = useState("");
  const [addingItem, setAddingItem] = useState(false);

  // Fetch real checklist data from MongoDB
  useEffect(() => {
    if (!caseId) return;

    const fetchChecklist = async () => {
      try {
        console.log("Fetching checklist for case:", caseId);
        setLoading(true);
        const normalizedRole =
          currentUser?.role === "Admin" || currentUser?.role === "admin"
            ? "Admin"
            : "Youth Helper";
        const res = await fetch(`${CASE_SERVICE_URL}/cases/${caseId}`, {
          headers: {
            "X-User-Id": (
              currentUser?.email ||
              currentUser?.user_id ||
              currentUser?.id ||
              "admin"
            ).toString(),
            "X-User-Email": (currentUser?.email || "").toString(),
            "X-User-Role": normalizedRole,
          },
        });
        if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
        const caseData = await res.json();

        console.log(
          "Case data received, checklist items:",
          caseData.checklist?.length || 0,
        );

        // Transform MongoDB checklist format to UI format
        const checklistItems = (caseData.checklist || []).map((item) => ({
          id: item.checklist_item_id,
          label: item.label,
          status: item.completed ? "Completed" : "Not Started",
          mandatory: item.is_mandatory,
          comments: item.comments || [],
        }));

        setItems(checklistItems);
      } catch (err) {
        console.error("Failed to fetch checklist:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchChecklist();

    // Listen for checklist updates from MCP tool execution
    const handleChecklistUpdate = (e) => {
      console.log("Checklist update event received:", e.detail);
      fetchChecklist();
    };
    window.addEventListener("checklistUpdate", handleChecklistUpdate);
    return () =>
      window.removeEventListener("checklistUpdate", handleChecklistUpdate);
  }, [caseId, currentUser]);

  // Status popup state
  const [popup, setPopup] = useState(null); // { item } | null
  const [popupStatus, setPopupStatus] = useState("Completed");
  const [popupComment, setPopupComment] = useState("");

  const openPopup = (item) => {
    setPopup(item);
    setPopupStatus(item.status === "Not Started" ? "Completed" : item.status);
    setPopupComment("");
  };

  const confirmStatusChange = () => {
    if (!popupComment.trim()) return;
    setItems((prev) =>
      prev.map((i) => (i.id === popup.id ? { ...i, status: popupStatus } : i)),
    );
    setComments((prev) => [
      ...prev,
      {
        id: Date.now(),
        text: `[${popup.label}] → ${popupStatus}: ${popupComment.trim()}`,
        time: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      },
    ]);
    setPopup(null);
    setPopupComment("");
  };

  const addItem = () => {
    if (newItem.trim()) {
      setItems((prev) => [
        ...prev,
        {
          id: Date.now(),
          label: newItem.trim(),
          status: "Not Started",
          mandatory: false,
        },
      ]);
      setNewItem("");
      setAddingItem(false);
    }
  };
  const addComment = () => {
    if (newComment.trim()) {
      setComments((prev) => [
        ...prev,
        {
          id: Date.now(),
          text: newComment.trim(),
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
      setNewComment("");
    }
  };

  const mandatoryDone = items
    .filter((i) => i.mandatory)
    .every((i) => i.status === "Completed");
  const completedCount = items.filter((i) => i.status === "Completed").length;
  const progress = items.length
    ? Math.round((completedCount / items.length) * 100)
    : 0;

  const renderItem = (item, accent = "#0672CB") => {
    const s = STATUS_STYLES[item.status] || STATUS_STYLES["Not Started"];
    const done = item.status === "Completed";
    return (
      <div
        key={item.id}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "7px 0",
          borderBottom: "1px solid #f8fafc",
        }}
      >
        <div
          onClick={() => openPopup(item)}
          style={{
            width: 20,
            height: 20,
            borderRadius: 5,
            border: done ? "none" : "2px solid #d1d5db",
            background: done ? accent : "#fff",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            transition: "all 0.15s",
          }}
        >
          {done && <Icon.Check size={12} style={{ color: "#fff" }} />}
        </div>
        <span
          style={{
            flex: 1,
            fontSize: 13,
            color: done ? "#94a3b8" : "#1e293b",
            textDecoration: done ? "line-through" : "none",
          }}
        >
          {item.label}
        </span>
        <button
          onClick={() => openPopup(item)}
          style={{
            background: s.bg,
            color: s.text,
            border: "none",
            borderRadius: 10,
            padding: "2px 8px",
            fontSize: 10,
            fontWeight: 700,
            cursor: "pointer",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {item.status}
        </button>
      </div>
    );
  };

  return (
    <>
      {/* ── Status-change popup modal ── */}
      {popup && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.5)",
            zIndex: 300,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 16,
              width: 360,
              padding: 24,
              boxShadow: "0 16px 48px rgba(0,0,0,0.25)",
            }}
          >
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
              Update checklist status
            </div>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 14 }}>
              "{popup.label}"
            </div>

            <div style={{ marginBottom: 12 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#64748b",
                  marginBottom: 6,
                  textTransform: "uppercase",
                  letterSpacing: "0.6px",
                }}
              >
                New Status
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {ITEM_STATUSES.map((s) => (
                  <button
                    key={s}
                    onClick={() => setPopupStatus(s)}
                    style={{
                      background:
                        popupStatus === s ? STATUS_STYLES[s].bg : "#f1f5f9",
                      color:
                        popupStatus === s ? STATUS_STYLES[s].text : "#64748b",
                      border:
                        popupStatus === s
                          ? `2px solid ${STATUS_STYLES[s].text}40`
                          : "2px solid transparent",
                      borderRadius: 20,
                      padding: "4px 12px",
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: "#64748b",
                  marginBottom: 6,
                  textTransform: "uppercase",
                  letterSpacing: "0.6px",
                }}
              >
                Comment <span style={{ color: "#dc2626" }}>*</span> (required)
              </div>
              <textarea
                autoFocus
                value={popupComment}
                onChange={(e) => setPopupComment(e.target.value)}
                placeholder="Describe what happened or why this status changed…"
                rows={3}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: 8,
                  border: "1px solid #d1d5db",
                  fontSize: 13,
                  outline: "none",
                  resize: "vertical",
                  boxSizing: "border-box",
                  fontFamily: "inherit",
                }}
              />
            </div>

            <div
              style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}
            >
              <button
                onClick={() => setPopup(null)}
                style={{
                  background: "#f1f5f9",
                  border: "none",
                  borderRadius: 8,
                  padding: "8px 16px",
                  cursor: "pointer",
                  fontSize: 13,
                  color: "#64748b",
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmStatusChange}
                disabled={!popupComment.trim()}
                style={{
                  background: popupComment.trim()
                    ? "linear-gradient(135deg, #0672CB, #0460a9)"
                    : "#e2e8f0",
                  color: popupComment.trim() ? "#fff" : "#94a3b8",
                  border: "none",
                  borderRadius: 8,
                  padding: "8px 20px",
                  cursor: popupComment.trim() ? "pointer" : "default",
                  fontSize: 13,
                  fontWeight: 600,
                  transition: "all 0.2s",
                }}
              >
                Save Status
              </button>
            </div>
          </div>
        </div>
      )}

      <div
        id="checklist-panel"
        style={{
          width: inlineMode ? "100%" : 320,
          background: "#fff",
          borderLeft: inlineMode ? "none" : "1px solid #e2e8f0",
          display: "flex",
          flexDirection: "column",
          overflowY: inlineMode ? "visible" : "auto",
          flexShrink: 0,
          border: highlight
            ? "2px solid #0672CB"
            : inlineMode
              ? "none"
              : "1px solid #e2e8f0",
          boxShadow: highlight ? "0 0 0 3px rgba(99,102,241,0.2)" : undefined,
          transition: "all 0.3s",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: inlineMode ? "16px 20px" : "14px 18px",
            borderBottom: "1px solid #f1f5f9",
            background: inlineMode ? "transparent" : "#fafafa",
            flexShrink: 0,
          }}
        >
          <div
            style={{
              fontWeight: 700,
              fontSize: 14,
              marginBottom: 12,
              display: "flex",
              alignItems: "center",
              gap: 8,
              color: "#1e293b",
              ...(inlineMode && {
                borderBottom: "1px solid #f1f5f9",
                paddingBottom: 12,
              }),
            }}
          >
            <Icon.CheckSquare size={16} color="#10b981" /> Case Checklist
          </div>
          <div
            style={{
              background: "#e2e8f0",
              borderRadius: 4,
              height: 6,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${progress}%`,
                height: "100%",
                background: mandatoryDone ? "#10b981" : "#0672CB",
                borderRadius: 4,
                transition: "width 0.4s",
              }}
            />
          </div>
          <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
            {completedCount}/{items.length} complete
            {mandatoryDone && " · All mandatory done"}
          </div>
        </div>

        {loading ? (
          <div
            style={{
              padding: "40px 18px",
              textAlign: "center",
              color: "#94a3b8",
              fontSize: 13,
            }}
          >
            <div
              style={{
                width: 24,
                height: 24,
                margin: "0 auto",
                border: "3px solid #e2e8f0",
                borderTop: "3px solid #0672CB",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
              }}
            ></div>
            <div style={{ marginTop: 12 }}>Loading checklist...</div>
          </div>
        ) : (
          <>
            {/* Mandatory items */}
            <div style={{ padding: "10px 18px 0" }}>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: "#dc2626",
                  textTransform: "uppercase",
                  letterSpacing: "0.8px",
                  marginBottom: 4,
                }}
              >
                Mandatory Steps
              </div>
              {items.filter((i) => i.mandatory).length === 0 && (
                <div
                  style={{
                    fontSize: 12,
                    color: "#94a3b8",
                    fontStyle: "italic",
                    padding: "8px 0",
                  }}
                >
                  No mandatory items yet.
                </div>
              )}
              {items
                .filter((i) => i.mandatory)
                .map((item) => renderItem(item, "#0672CB"))}
            </div>
            {/* Custom items */}
            {items.filter((i) => !i.mandatory).length > 0 && (
              <div style={{ padding: "10px 18px 0" }}>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#0672CB",
                    textTransform: "uppercase",
                    letterSpacing: "0.8px",
                    marginBottom: 4,
                  }}
                >
                  Custom Items
                </div>
                {items
                  .filter((i) => !i.mandatory)
                  .map((item) => renderItem(item, "#0460a9"))}
              </div>
            )}
          </>
        )}

        {/* Add custom item */}
        {!loading && (
          <div style={{ padding: "10px 18px" }}>
            {addingItem ? (
              <div style={{ display: "flex", gap: 6 }}>
                <input
                  autoFocus
                  value={newItem}
                  onChange={(e) => setNewItem(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addItem()}
                  placeholder="New checklist item…"
                  style={{
                    flex: 1,
                    padding: "6px 10px",
                    borderRadius: 8,
                    border: "1px solid #d1d5db",
                    fontSize: 13,
                    outline: "none",
                  }}
                />
                <button
                  onClick={addItem}
                  style={{
                    background: "#0672CB",
                    color: "#fff",
                    border: "none",
                    borderRadius: 8,
                    padding: "4px 12px",
                    cursor: "pointer",
                    fontSize: 13,
                  }}
                >
                  +
                </button>
                <button
                  onClick={() => {
                    setAddingItem(false);
                    setNewItem("");
                  }}
                  style={{
                    background: "#f1f5f9",
                    border: "none",
                    borderRadius: 8,
                    padding: "4px 8px",
                    cursor: "pointer",
                    color: "#64748b",
                  }}
                >
                  <Icon.X size={14} />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setAddingItem(true)}
                style={{
                  width: "100%",
                  background: "#f8fafc",
                  border: "1px dashed #cbd5e1",
                  borderRadius: 8,
                  padding: "7px",
                  cursor: "pointer",
                  color: "#0672CB",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                + Add custom item
              </button>
            )}
          </div>
        )}

        {/* Comments */}
        {!loading && (
          <div
            style={{
              borderTop: "1px solid #e2e8f0",
              padding: "12px 18px",
              flex: 1,
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#64748b",
                textTransform: "uppercase",
                letterSpacing: "0.8px",
                marginBottom: 8,
              }}
            >
              <Icon.MessageCircle
                size={11}
                style={{ display: "inline-block", marginRight: 4 }}
              />{" "}
              Comments
            </div>
            <div style={{ maxHeight: 150, overflowY: "auto", marginBottom: 8 }}>
              {comments.length === 0 && (
                <div
                  style={{
                    fontSize: 12,
                    color: "#94a3b8",
                    fontStyle: "italic",
                  }}
                >
                  No comments yet.
                </div>
              )}
              {comments.map((c) => (
                <div
                  key={c.id}
                  style={{
                    background: "#f8fafc",
                    borderRadius: 8,
                    padding: "7px 10px",
                    marginBottom: 6,
                    border: "1px solid #f1f5f9",
                  }}
                >
                  <div style={{ fontSize: 12, color: "#475569" }}>{c.text}</div>
                  <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 3 }}>
                    {c.time} · {displayName}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <input
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addComment()}
                placeholder="Add a comment…"
                style={{
                  flex: 1,
                  padding: "7px 10px",
                  borderRadius: 8,
                  border: "1px solid #d1d5db",
                  fontSize: 12,
                  outline: "none",
                }}
              />
              <button
                onClick={addComment}
                style={{
                  background: "#0672CB",
                  color: "#fff",
                  border: "none",
                  borderRadius: 8,
                  padding: "4px 12px",
                  cursor: "pointer",
                  fontSize: 13,
                }}
              >
                <Icon.Send size={13} />
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ─── CHATBOT PANEL (right-side slide-out) ────────────────────────────
function ChatbotPanel({
  assignedCases,
  highlight,
  open,
  onClose,
  selectedCase: ctxCase,
  currentUser: cpUser,
}) {
  const currentUser = cpUser || {
    user_id: "unknown",
    id: "unknown",
    role: "Youth Helper",
  };
  const currentUserHeaderId = (
    currentUser?.email || currentUser?.user_id || currentUser?.id || ""
  )
    .toString()
    .trim();
  const currentUserRole =
    currentUser?.role === "Admin" || currentUser?.role === "admin"
      ? "Admin"
      : "Youth Helper";
  const [messages, setMessages] = useState([
    {
      role: "bot",
      text: "Hello! I'm the SCS Recommendation Assistant with **full access to SCS protocols and case data**.\n\nI can help you with:\n- Updating checklists\n- Adding case notes\n- Scheduling follow-ups\n- Requesting reassignments\n- Finding similar cases\n\nAttach a case using the button, then ask me anything!\n\n*I provide guidance and can execute actions with your approval. All final decisions are yours.*",
      actions: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [attachedCase, setAttachedCase] = useState(null);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-attach the case currently open in the detail panel
  useEffect(() => {
    if (ctxCase && assignedCases.some((c) => c.id === ctxCase.id)) {
      setAttachedCase(ctxCase);
    }
  }, [ctxCase]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const t = text || input;
    if (!t.trim() || loading) return;
    setMessages((prev) => [
      ...prev,
      { role: "user", text: t, attached: attachedCase },
    ]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch(`${CHATBOT_SERVICE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": currentUserHeaderId,
          "X-User-Email": (currentUser?.email || "").toString(),
          "X-User-Role": currentUserRole,
        },
        body: JSON.stringify({
          message: t,
          case_id: attachedCase?.code || null,
          case_info: attachedCase
            ? {
                code: attachedCase.code,
                category: attachedCase.category,
                riskLevel: attachedCase.riskLevel,
                status: attachedCase.status,
                signals: attachedCase.signals || [],
              }
            : null,
          user_id: currentUserHeaderId,
          execute_tools: false, // Never auto-execute, require approval
          conversation_history: messages.slice(-6).map((m) => ({
            role: m.role === "user" ? "user" : "assistant",
            content: m.text,
          })),
        }),
      });
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data = await res.json();

      // Check if response includes tool calls (agentic actions)
      if (data.tool_calls && data.tool_calls.length > 0) {
        // Convert tool_calls to actions format for existing UI
        const actions = data.tool_calls.map((tc) => ({
          action_type: tc.tool,
          payload: tc.parameters,
          reasoning: data.reasoning || "Recommended based on SCS protocols",
        }));

        // Use the formatted response from backend (already user-friendly)
        let responseText = data.response || "I've prepared some actions for you to review.";

        setMessages((prev) => [
          ...prev,
          {
            role: "bot",
            text: responseText,
            actions: actions,
            similar: data.similar_cases || [],
            toolCalls: data.tool_calls,
          },
        ]);
      } else {
        // Regular guidance response
        setMessages((prev) => [
          ...prev,
          {
            role: "bot",
            text:
              data.response || data.response_text || data.message || "Done.",
            actions: data.proposed_actions || [],
            similar: data.similar_cases || [],
          },
        ]);
      }
    } catch (err) {
      console.error("Chatbot error:", err);
      // Fallback: static response
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          text: getChatbotResponse(t, attachedCase),
          actions: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const executeAction = async (action) => {
    const toolMap = {
      add_checklist_item: "add_checklist_item",
      create_checklist_item: "add_checklist_item", // Map singular create to add
      create_checklist_items: "add_checklist_items", // Map plural to bulk endpoint
      add_checklist_items: "add_checklist_items", // Direct mapping for bulk
      update_checklist_item_status: "update_checklist_item_status",
      add_case_note: "add_case_note",
      schedule_followup: "schedule_followup",
      update_case_status: "update_case_status",
      update_priority: "update_priority",
      request_reassignment: "request_reassignment",
      assign_case: "assign_case",
      update_checklist: "update_checklist_item_status",
      add_comment: "add_case_note",
      schedule_review: "schedule_followup",
      query_case_details: "query_case_details",
      query_instagram_data: "query_instagram_data",
      query_similar_cases: "get_similar_cases",
    };
    const tool = toolMap[action.action_type] || action.action_type;

    console.log("Executing action:", {
      action_type: action.action_type,
      tool,
      payload: action.payload,
    });

    // Special handling for creating multiple checklist items
    if (
      (action.action_type === "create_checklist_items" ||
        action.action_type === "add_checklist_items") &&
      action.payload?.items &&
      Array.isArray(action.payload.items)
    ) {
      console.log(
        `Creating ${action.payload.items.length} checklist items via bulk endpoint`,
      );
      try {
        const res = await fetch(
          `${MCP_SERVICE_URL}/tools/add_checklist_items`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-User-Id": currentUserHeaderId,
              "X-User-Email": (currentUser?.email || "").toString(),
              "X-User-Role": currentUserRole,
            },
            body: JSON.stringify({
              case_id: action.payload.case_id,
              items: action.payload.items.map((item) => ({
                label: item.label || item,
                is_mandatory: item.is_mandatory || false,
              })),
            }),
          },
        );
        const data = await res.json();

        // Trigger checklist refresh
        window.dispatchEvent(
          new CustomEvent("checklistUpdate", { detail: data }),
        );

        return {
          ok: res.ok,
          data: data,
        };
      } catch (e) {
        console.error("Error creating checklist items:", e);
        return {
          ok: false,
          data: { error: String(e) },
        };
      }
    }

    // Transform payload for singular checklist item creation
    let requestPayload = action.payload || {};
    if (
      (action.action_type === "create_checklist_item" ||
        action.action_type === "add_checklist_item") &&
      tool === "add_checklist_item"
    ) {
      // Ensure payload has correct structure: {case_id, label, is_mandatory?}
      const label =
        action.payload.label ||
        action.payload.item_text ||
        action.payload.item ||
        action.payload.text ||
        "";

      // Validate label is not empty
      if (!label.trim()) {
        console.error(
          "Cannot create checklist item: label is empty",
          action.payload,
        );
        return {
          ok: false,
          data: {
            error:
              "Checklist item label cannot be empty. Please provide a valid label.",
          },
        };
      }

      requestPayload = {
        case_id: action.payload.case_id,
        label: label.trim(),
        is_mandatory: action.payload.is_mandatory || false,
      };
      console.log("Transformed checklist payload:", requestPayload);
    }

    try {
      const res = await fetch(`${MCP_SERVICE_URL}/tools/${tool}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-Id": currentUserHeaderId,
          "X-User-Email": (currentUser?.email || "").toString(),
          "X-User-Role": currentUserRole,
        },
        body: JSON.stringify(requestPayload),
      });
      const data = await res.json();

      console.log("Action result:", { ok: res.ok, status: res.status, data });

      // Handle UI updates based on action type
      if (res.ok && data) {
        if (
          tool === "update_checklist_item_status" ||
          tool === "add_checklist_item"
        ) {
          // Trigger checklist refresh event
          console.log("Dispatching checklistUpdate event");
          window.dispatchEvent(
            new CustomEvent("checklistUpdate", { detail: data }),
          );
        } else if (tool === "schedule_followup") {
          // Show notification
          const reviewDate =
            action.payload?.review_date || action.payload?.followup_date;
          if (reviewDate) {
            setTimeout(() => alert(`Review scheduled for ${reviewDate}`), 100);
          }
        } else if (tool === "request_reassignment") {
          // Show confirmation
          setTimeout(
            () => alert("Reassignment request submitted to team lead"),
            100,
          );
        }
      }

      return { ok: res.ok, data };
    } catch (e) {
      console.error("MCP tool execution error:", e);
      return { ok: false, data: { error: String(e) } };
    }
  };

  const renderText = (text) => {
    return text.split("\n").map((line, i) => {
      let rendered = line
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, '<em style="color:#94a3b8">$1</em>');
      if (line.startsWith("| ")) {
        const cells = line.split("|").filter((c) => c.trim());
        if (line.includes("---")) return null;
        return (
          <div
            key={i}
            style={{
              display: "flex",
              borderBottom: "1px solid #e2e8f0",
              background: i === 1 ? "#f1f5f9" : "transparent",
            }}
          >
            {cells.map((c, j) => (
              <div
                key={j}
                style={{
                  flex: 1,
                  padding: "4px 6px",
                  fontSize: 11,
                  color: "#475569",
                }}
              >
                {c.trim()}
              </div>
            ))}
          </div>
        );
      }
      return (
        <div
          key={i}
          style={{
            fontSize: 13,
            color: "#475569",
            lineHeight: 1.55,
            minHeight: line === "" ? 10 : "auto",
          }}
          dangerouslySetInnerHTML={{ __html: rendered }}
        />
      );
    });
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          onClick={onClose}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15,23,42,0.3)",
            zIndex: 155,
            transition: "opacity 0.3s",
          }}
        />
      )}

      {/* Slide-out panel */}
      <div
        id="chatbot-area"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          height: "100vh",
          width: 550,
          background: "#fff",
          boxShadow: "-8px 0 40px rgba(0,0,0,0.18)",
          border: highlight ? "2px solid #0672CB" : "none",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          zIndex: 156,
          transition: "transform 0.35s cubic-bezier(0.4,0,0.2,1)",
          transform: open ? "translateX(0)" : "translateX(100%)",
        }}
      >
        {/* Header */}
        <div
          style={{
            background: "linear-gradient(135deg, #1e293b, #0f172a)",
            color: "#fff",
            padding: "14px 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "linear-gradient(135deg, #0672CB, #0460a9)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon.MessageCircle size={16} style={{ color: "#fff" }} />
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                SCS Recommendation Assistant
              </div>
              <div style={{ fontSize: 10, color: "#94a3b8" }}>
                Advisory + Agentic · RAG-backed
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "rgba(255,255,255,0.15)",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "#fff",
              borderRadius: 8,
              width: 36,
              height: 36,
              cursor: "pointer",
              fontSize: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginLeft: 16,
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(239,68,68,0.9)";
              e.currentTarget.style.transform = "scale(1.05)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "rgba(255,255,255,0.15)";
              e.currentTarget.style.transform = "scale(1)";
            }}
          >
            <Icon.X size={18} />
          </button>
        </div>

        {/* Attached case badge */}
        {attachedCase && (
          <div
            style={{
              background: "#eef2ff",
              padding: "6px 14px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: "1px solid #c7d2fe",
              flexShrink: 0,
            }}
          >
            <div style={{ fontSize: 12, color: "#4338ca" }}>
              <Icon.Paperclip
                size={12}
                style={{ display: "inline", marginRight: 4 }}
              />
              <strong>{attachedCase.code}</strong> — {attachedCase.category}{" "}
              (Risk{" "}
              {attachedCase.current_risk_score?.toFixed(1) ??
                attachedCase.riskLevel}
              %)
            </div>
            <button
              onClick={() => setAttachedCase(null)}
              style={{
                background: "none",
                border: "none",
                color: "#0672CB",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              <Icon.X size={13} />
            </button>
          </div>
        )}

        {/* Messages */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: 14,
            display: "flex",
            flexDirection: "column",
            gap: 12,
          }}
        >
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: m.role === "user" ? "flex-end" : "flex-start",
                gap: 8,
              }}
            >
              <div
                style={{
                  maxWidth: "90%",
                  background:
                    m.role === "user"
                      ? "linear-gradient(135deg, #0672CB, #0460a9)"
                      : "#f8fafc",
                  color: m.role === "user" ? "#fff" : "#1e293b",
                  borderRadius:
                    m.role === "user"
                      ? "16px 16px 4px 16px"
                      : "16px 16px 16px 4px",
                  padding: "10px 14px",
                  border: m.role === "bot" ? "1px solid #e2e8f0" : "none",
                }}
              >
                {m.attached && m.role === "user" && (
                  <div
                    style={{
                      fontSize: 10,
                      color: "rgba(255,255,255,0.7)",
                      marginBottom: 3,
                    }}
                  >
                    <Icon.Paperclip
                      size={10}
                      style={{ display: "inline", marginRight: 3 }}
                    />{" "}
                    {m.attached.code}
                  </div>
                )}
                {m.role === "user" ? (
                  <div style={{ fontSize: 13 }}>{m.text}</div>
                ) : (
                  <div>{renderText(m.text)}</div>
                )}
              </div>

              {/* Proposed action cards */}
              {m.role === "bot" && m.actions?.length > 0 && (
                <div
                  style={{
                    maxWidth: "95%",
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      color: "#64748b",
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <Icon.Zap size={11} /> Proposed Actions — review before
                    approving
                  </div>
                  {m.actions.map((action, ai) => (
                    <ActionCard
                      key={ai}
                      action={action}
                      onApprove={executeAction}
                    />
                  ))}
                </div>
              )}

              {/* Similar cases */}
              {m.role === "bot" && m.similar?.length > 0 && (
                <div
                  style={{
                    maxWidth: "95%",
                    background: "#f0fdf4",
                    border: "1px solid #86efac",
                    borderRadius: 10,
                    padding: "8px 12px",
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      color: "#15803d",
                      fontWeight: 600,
                      marginBottom: 4,
                    }}
                  >
                    <Icon.Link
                      size={11}
                      style={{ display: "inline", marginRight: 3 }}
                    />{" "}
                    Similar Cases
                  </div>
                  {m.similar.map((s, si) => (
                    <div
                      key={si}
                      style={{
                        fontSize: 12,
                        color: "#475569",
                        padding: "2px 0",
                      }}
                    >
                      <strong>{s.case_id}</strong> — {s.category} (Risk{" "}
                      {s.risk_level}) · {s.reason || ""}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                color: "#94a3b8",
                fontSize: 13,
              }}
            >
              <div style={{ display: "flex", gap: 4 }}>
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      background: "#0672CB",
                      animation: `bounce ${0.6 + i * 0.15}s infinite alternate`,
                      opacity: 0.7,
                    }}
                  />
                ))}
              </div>
              Assistant is thinking…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Quick actions */}
        <div
          style={{
            padding: "6px 12px 0",
            borderTop: "1px solid #f1f5f9",
            display: "flex",
            gap: 6,
            overflowX: "auto",
            paddingBottom: 4,
            flexShrink: 0,
          }}
        >
          {PRESET_QUESTIONS.map((p, i) => (
            <button
              key={i}
              onClick={() => send(p.q)}
              style={{
                whiteSpace: "nowrap",
                background: "#f1f5f9",
                border: "1px solid #e2e8f0",
                borderRadius: 20,
                padding: "5px 12px",
                fontSize: 11,
                cursor: "pointer",
                color: "#475569",
                display: "flex",
                alignItems: "center",
                gap: 3,
                flexShrink: 0,
                fontWeight: 500,
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "#e0e7ff")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "#f1f5f9")
              }
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Input row */}
        <div
          style={{
            padding: "8px 12px 16px",
            display: "flex",
            gap: 8,
            alignItems: "center",
            flexShrink: 0,
          }}
        >
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setShowAttachMenu(!showAttachMenu)}
              title="Attach case"
              style={{
                background: "#f1f5f9",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                width: 36,
                height: 36,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: attachedCase ? "#0672CB" : "#94a3b8",
              }}
            >
              <Icon.Paperclip size={16} />
            </button>
            {showAttachMenu && (
              <div
                style={{
                  position: "absolute",
                  bottom: "calc(100% + 6px)",
                  left: 0,
                  background: "#fff",
                  borderRadius: 12,
                  boxShadow: "0 8px 30px rgba(0,0,0,0.18)",
                  width: 250,
                  zIndex: 10,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "8px 12px 4px",
                    fontSize: 11,
                    fontWeight: 700,
                    color: "#94a3b8",
                    textTransform: "uppercase",
                    letterSpacing: "0.8px",
                  }}
                >
                  Attach a case
                </div>
                {assignedCases.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => {
                      setAttachedCase(c);
                      setShowAttachMenu(false);
                    }}
                    style={{
                      width: "100%",
                      textAlign: "left",
                      background:
                        attachedCase?.id === c.id ? "#eef2ff" : "none",
                      border: "none",
                      padding: "8px 12px",
                      cursor: "pointer",
                      fontSize: 12,
                      color: "#1e293b",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = "#f8fafc")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background =
                        attachedCase?.id === c.id ? "#eef2ff" : "none")
                    }
                  >
                    <RiskBadge
                      level={c.riskLevel}
                      score={c.current_risk_score}
                    />
                    <span style={{ fontWeight: 600 }}>{c.code}</span>
                    <span style={{ color: "#94a3b8", fontSize: 11 }}>
                      {c.category}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask for guidance…"
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: 10,
              border: "1px solid #d1d5db",
              fontSize: 13,
              outline: "none",
            }}
          />
          <button
            onClick={() => send()}
            disabled={loading}
            style={{
              background: "linear-gradient(135deg, #0672CB, #0460a9)",
              color: "#fff",
              border: "none",
              borderRadius: 10,
              width: 36,
              height: 36,
              cursor: "pointer",
              fontSize: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: loading ? 0.6 : 1,
            }}
          >
            <Icon.Send size={16} />
          </button>
        </div>
      </div>
    </>
  );
}

// ─── ACTION CARD (approve / edit / cancel a proposed action) ──────────────────
function ActionCard({ action, onApprove }) {
  // Helper to extract label from various possible field names
  const getInitialLabel = () => {
    if (
      (action.action_type === "create_checklist_items" ||
        action.action_type === "add_checklist_items") &&
      action.payload?.items
    ) {
      return action.payload.items
        .map((item) => (typeof item === "string" ? item : item.label))
        .join("\n");
    }
    return (
      action.payload?.label ||
      action.payload?.item_text ||
      action.payload?.item ||
      action.payload?.text ||
      ""
    );
  };

  const [status, setStatus] = useState("pending"); // pending | approving | approved | rejected | editing
  const [editPayload, setEditPayload] = useState(
    JSON.stringify(action.payload || {}, null, 2),
  );
  const [editLabel, setEditLabel] = useState(() => getInitialLabel());
  const [resultMsg, setResultMsg] = useState("");
  const [editError, setEditError] = useState("");

  const approve = async (overridePayload) => {
    setStatus("approving");
    try {
      const actionToRun = overridePayload
        ? {
            ...action,
            payload:
              typeof overridePayload === "string"
                ? JSON.parse(overridePayload)
                : overridePayload,
          }
        : action;
      const { ok, data } = await onApprove(actionToRun);
      if (ok) {
        setResultMsg(data?.message || "Executed successfully");
        setStatus("approved");
      } else {
        setResultMsg(
          `Failed: ${data?.detail || data?.error || "Unknown error"}`,
        );
        setStatus("rejected");
      }
    } catch (err) {
      setResultMsg(`Error: ${err.message}`);
      setStatus("rejected");
    }
  };

  const handleEdit = () => {
    setEditError("");
    setStatus("editing");
    // Re-initialize edit label to ensure it has the current value
    if (
      action.action_type === "add_checklist_item" ||
      action.action_type === "create_checklist_item"
    ) {
      const label =
        action.payload?.label ||
        action.payload?.item_text ||
        action.payload?.item ||
        action.payload?.text ||
        "";
      setEditLabel(label);
      if (!label) {
        setEditError("No label found to edit");
      }
    } else if (
      (action.action_type === "create_checklist_items" ||
        action.action_type === "add_checklist_items") &&
      action.payload?.items
    ) {
      // For multiple items, join them into lines
      const itemsText = action.payload.items
        .map((item) => (typeof item === "string" ? item : item.label))
        .join("\n");
      setEditLabel(itemsText);
      if (!itemsText) {
        setEditError("No items found to edit");
      }
    }
  };

  const handleApproveEdited = () => {
    try {
      if (
        action.action_type === "add_checklist_item" ||
        action.action_type === "create_checklist_item"
      ) {
        // For single checklist item, just update the label in the payload
        const updatedPayload = { ...action.payload, label: editLabel.trim() };
        if (!editLabel.trim()) {
          setEditError("Label cannot be empty");
          return;
        }
        setEditError("");
        approve(updatedPayload);
      } else if (
        action.action_type === "create_checklist_items" ||
        action.action_type === "add_checklist_items"
      ) {
        // For multiple items, parse the text (one per line)
        const lines = editLabel
          .split("\n")
          .map((l) => l.trim())
          .filter((l) => l);
        if (lines.length === 0) {
          setEditError("At least one item is required");
          return;
        }
        const updatedPayload = {
          ...action.payload,
          items: lines.map((line) => ({
            label: line,
            is_mandatory: false, // Default to optional when editing
          })),
        };
        setEditError("");
        approve(updatedPayload);
      } else {
        // For other actions, use JSON editing
        JSON.parse(editPayload); // Validate JSON
        setEditError("");
        approve(editPayload);
      }
    } catch (err) {
      setEditError("Invalid JSON format");
    }
  };

  const typeLabel =
    {
      add_checklist_item: "Add Checklist Item",
      create_checklist_item: "Add Checklist Item",
      create_checklist_items: "Add Checklist Items",
      add_checklist_items: "Add Checklist Items",
      update_checklist_item_status: "Update Checklist Status",
      add_case_note: "Add Case Note",
      schedule_followup: "Schedule Follow-up",
      update_case_status: "Update Case Status",
      update_priority: "Update Priority",
      request_reassignment: "Request Reassignment",
      assign_case: "Assign Case",
    }[action.action_type] || action.action_type;

  const accentColor =
    status === "approved"
      ? "#10b981"
      : status === "rejected"
        ? "#dc2626"
        : status === "editing"
          ? "#f59e0b"
          : "#0672CB";
  const iconColor =
    status === "approved"
      ? "#10b981"
      : status === "rejected"
        ? "#dc2626"
        : "#0672CB";

  return (
    <div
      style={{
        background: "#fff",
        border: `1.5px solid ${accentColor}20`,
        borderLeft: `4px solid ${accentColor}`,
        borderRadius: 12,
        padding: "14px 16px",
        fontSize: 12,
        boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
        transition: "all 0.2s",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 8,
        }}
      >
        <div
          style={{
            fontWeight: 700,
            color: accentColor,
            fontSize: 12,
            textTransform: "uppercase",
            letterSpacing: "0.5px",
            flex: 1,
          }}
        >
          {typeLabel}
        </div>
        {status === "approved" && (
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#10b981",
              background: "#d1fae5",
              padding: "3px 8px",
              borderRadius: 4,
            }}
          >
            APPROVED
          </div>
        )}
        {status === "rejected" && (
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#dc2626",
              background: "#fee2e2",
              padding: "3px 8px",
              borderRadius: 4,
            }}
          >
            REJECTED
          </div>
        )}
        {status === "editing" && (
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#f59e0b",
              background: "#fef3c7",
              padding: "3px 8px",
              borderRadius: 4,
            }}
          >
            EDITING
          </div>
        )}
      </div>
      <div
        style={{
          color: "#475569",
          marginBottom: 10,
          lineHeight: 1.5,
          fontSize: 13,
        }}
      >
        {action.description}
      </div>

      {status === "editing" ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "#f59e0b",
              marginBottom: 2,
            }}
          >
            Edit Action Details:
          </div>

          {action.action_type === "add_checklist_item" ||
          action.action_type === "create_checklist_item" ? (
            // Simplified UI for single checklist item - just edit the label
            <>
              <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>
                Checklist Item:
              </div>
              <input
                type="text"
                value={editLabel}
                onChange={(e) => {
                  setEditLabel(e.target.value);
                  setEditError("");
                }}
                placeholder="Enter checklist item label..."
                style={{
                  width: "100%",
                  fontSize: 13,
                  borderRadius: 8,
                  border: editError
                    ? "1.5px solid #dc2626"
                    : "1.5px solid #d1d5db",
                  padding: "10px 12px",
                  outline: "none",
                  boxSizing: "border-box",
                  background: "#fafafa",
                  fontFamily: "inherit",
                }}
              />
              {action.payload?.is_mandatory !== undefined && (
                <div
                  style={{
                    fontSize: 11,
                    color: "#64748b",
                    marginTop: 4,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span style={{ fontWeight: 600 }}>Type:</span>
                  <span
                    style={{
                      background: action.payload.is_mandatory
                        ? "#fef3c7"
                        : "#e0e7ff",
                      color: action.payload.is_mandatory
                        ? "#92400e"
                        : "#4338ca",
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 10,
                      fontWeight: 600,
                    }}
                  >
                    {action.payload.is_mandatory ? "Mandatory" : "Optional"}
                  </span>
                </div>
              )}
            </>
          ) : action.action_type === "create_checklist_items" ||
            action.action_type === "add_checklist_items" ? (
            // Textarea for multiple checklist items (one per line)
            <>
              <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>
                Checklist Items (one per line):
              </div>
              <textarea
                value={editLabel}
                onChange={(e) => {
                  setEditLabel(e.target.value);
                  setEditError("");
                }}
                placeholder="Enter checklist items, one per line..."
                rows={6}
                style={{
                  width: "100%",
                  fontSize: 13,
                  borderRadius: 8,
                  border: editError
                    ? "1.5px solid #dc2626"
                    : "1.5px solid #d1d5db",
                  padding: "10px 12px",
                  outline: "none",
                  boxSizing: "border-box",
                  background: "#fafafa",
                  fontFamily: "inherit",
                  lineHeight: 1.5,
                  resize: "vertical",
                }}
              />
              <div
                style={{ fontSize: 10, color: "#94a3b8", fontStyle: "italic" }}
              >
                Tip: Each line will become a separate checklist item
              </div>
            </>
          ) : (
            // JSON editor for other action types
            <textarea
              value={editPayload}
              onChange={(e) => {
                setEditPayload(e.target.value);
                setEditError("");
              }}
              rows={6}
              style={{
                width: "100%",
                fontFamily: "'Monaco', 'Courier New', monospace",
                fontSize: 11,
                borderRadius: 8,
                border: editError
                  ? "1.5px solid #dc2626"
                  : "1.5px solid #d1d5db",
                padding: "10px",
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box",
                background: "#fafafa",
              }}
            />
          )}

          {editError && (
            <div
              style={{
                color: "#dc2626",
                fontSize: 11,
                fontWeight: 600,
                background: "#fee2e2",
                padding: "6px 8px",
                borderRadius: 6,
              }}
            >
              Error: {editError}
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleApproveEdited}
              style={{
                flex: 1,
                background: "#10b981",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                padding: "9px 14px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "#059669")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "#10b981")
              }
            >
              Approve Edited
            </button>
            <button
              onClick={() => {
                setStatus("pending");
                setEditError("");
              }}
              style={{
                flex: 1,
                background: "#fff",
                color: "#64748b",
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                padding: "9px 14px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "#f8fafc")
              }
              onMouseLeave={(e) => (e.currentTarget.style.background = "#fff")}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : status === "approving" ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: "#0672CB",
            fontStyle: "italic",
            fontSize: 12,
            padding: "8px 0",
          }}
        >
          <div
            style={{
              width: 16,
              height: 16,
              border: "2px solid #0672CB",
              borderTop: "2px solid transparent",
              borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }}
          ></div>
          <span>Executing action...</span>
        </div>
      ) : status === "approved" || status === "rejected" ? (
        <div
          style={{
            background: status === "approved" ? "#d1fae5" : "#fee2e2",
            color: accentColor,
            fontWeight: 600,
            fontSize: 12,
            padding: "8px 12px",
            borderRadius: 8,
            border: `1px solid ${accentColor}30`,
          }}
        >
          {resultMsg}
        </div>
      ) : (
        <>
          {/* Display clean preview based on action type */}
          {action.payload &&
            (() => {
              // For multiple checklist items - show list
              if (
                (action.action_type === "create_checklist_items" ||
                  action.action_type === "add_checklist_items") &&
                action.payload.items &&
                Array.isArray(action.payload.items)
              ) {
                return (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      padding: "10px 12px",
                      marginBottom: 10,
                      fontSize: 13,
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 600,
                        color: "#1e293b",
                        marginBottom: 8,
                      }}
                    >
                      Items to add ({action.payload.items.length}):
                    </div>
                    {action.payload.items.map((item, idx) => {
                      const label =
                        typeof item === "string" ? item : item.label;
                      const isMandatory =
                        typeof item === "object" ? item.is_mandatory : false;
                      return (
                        <div
                          key={idx}
                          style={{
                            color: "#475569",
                            lineHeight: 1.5,
                            marginBottom:
                              idx < action.payload.items.length - 1 ? 8 : 0,
                            paddingLeft: 8,
                            borderLeft: "2px solid #e2e8f0",
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <span style={{ color: "#94a3b8", fontWeight: 600 }}>
                            {idx + 1}.
                          </span>
                          <span>{label}</span>
                          {isMandatory && (
                            <span
                              style={{
                                background: "#fef3c7",
                                color: "#92400e",
                                padding: "2px 6px",
                                borderRadius: 4,
                                fontSize: 10,
                                fontWeight: 600,
                              }}
                            >
                              Mandatory
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              }

              // For single checklist item - show just the label
              if (
                action.action_type === "add_checklist_item" ||
                action.action_type === "create_checklist_item"
              ) {
                const label =
                  action.payload.label ||
                  action.payload.item_text ||
                  action.payload.item ||
                  action.payload.text ||
                  "";
                if (label) {
                  return (
                    <div
                      style={{
                        background: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        borderRadius: 8,
                        padding: "10px 12px",
                        marginBottom: 10,
                        fontSize: 13,
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 600,
                          color: "#1e293b",
                          marginBottom: 4,
                        }}
                      >
                        Item to add:
                      </div>
                      <div style={{ color: "#475569", lineHeight: 1.5 }}>
                        "{label}"
                      </div>
                      {action.payload.is_mandatory !== undefined && (
                        <div
                          style={{
                            marginTop: 6,
                            fontSize: 11,
                            color: "#64748b",
                          }}
                        >
                          <span
                            style={{
                              background: action.payload.is_mandatory
                                ? "#fef3c7"
                                : "#e0e7ff",
                              color: action.payload.is_mandatory
                                ? "#92400e"
                                : "#4338ca",
                              padding: "2px 8px",
                              borderRadius: 4,
                              fontSize: 10,
                              fontWeight: 600,
                            }}
                          >
                            {action.payload.is_mandatory
                              ? "Mandatory"
                              : "Optional"}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                }
              }

              // For update status - show just the key info
              if (action.action_type === "update_checklist_item_status") {
                return (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      padding: "10px 12px",
                      marginBottom: 10,
                      fontSize: 13,
                    }}
                  >
                    <div style={{ color: "#475569", lineHeight: 1.5 }}>
                      Mark item{" "}
                      <strong>#{action.payload.checklist_item_id}</strong> as{" "}
                      {action.payload.completed ? "completed" : "incomplete"}
                    </div>
                    {action.payload.comment && (
                      <div
                        style={{
                          marginTop: 6,
                          fontSize: 11,
                          color: "#64748b",
                          fontStyle: "italic",
                        }}
                      >
                        "{action.payload.comment}"
                      </div>
                    )}
                  </div>
                );
              }

              // For case notes - show just the content
              if (
                action.action_type === "add_case_note" &&
                action.payload.content
              ) {
                return (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      padding: "10px 12px",
                      marginBottom: 10,
                      fontSize: 13,
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 600,
                        color: "#1e293b",
                        marginBottom: 4,
                      }}
                    >
                      Note to add:
                    </div>
                    <div style={{ color: "#475569", lineHeight: 1.5 }}>
                      "{action.payload.content}"
                    </div>
                  </div>
                );
              }

              // For other actions - show clean key-value pairs (not raw JSON)
              const displayKeys = Object.keys(action.payload).filter(
                (k) => k !== "case_id",
              );
              if (displayKeys.length > 0) {
                return (
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      padding: "10px 12px",
                      marginBottom: 10,
                      fontSize: 12,
                    }}
                  >
                    {displayKeys.map((key) => (
                      <div
                        key={key}
                        style={{ marginBottom: 4, display: "flex", gap: 6 }}
                      >
                        <span
                          style={{
                            fontWeight: 600,
                            color: "#64748b",
                            textTransform: "capitalize",
                          }}
                        >
                          {key.replace(/_/g, " ")}:
                        </span>
                        <span style={{ color: "#475569" }}>
                          {String(action.payload[key])}
                        </span>
                      </div>
                    ))}
                  </div>
                );
              }
              return null;
            })()}

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => approve()}
              style={{
                flex: 1,
                background: "#10b981",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                padding: "9px 14px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "#059669")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "#10b981")
              }
            >
              Approve
            </button>
            <button
              onClick={handleEdit}
              style={{
                flex: 1,
                background: "#fff",
                color: "#64748b",
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                padding: "9px 14px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#f8fafc";
                e.currentTarget.style.borderColor = "#cbd5e1";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#fff";
                e.currentTarget.style.borderColor = "#e2e8f0";
              }}
            >
              Edit
            </button>
            <button
              onClick={() => {
                setStatus("rejected");
                setResultMsg("Action cancelled");
              }}
              style={{
                background: "#fff",
                color: "#dc2626",
                border: "1px solid #fecaca",
                borderRadius: 6,
                padding: "9px 14px",
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "#fef2f2")
              }
              onMouseLeave={(e) => (e.currentTarget.style.background = "#fff")}
            >
              Cancel
            </button>
          </div>
        </>
      )}
    </div>
  );
}
// ─── LLM SUMMARY DIALOG ─────────────────────────────────────────────────
function LlmSummaryDialog({ open, onClose, summary, onGenerate }) {
  if (!summary || !open) return null;

  const formatDate = (dateStr) => {
    try {
      return new Date(dateStr).toLocaleString("en-SG", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.7)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: 20,
          width: "90%",
          maxWidth: 700,
          maxHeight: "85vh",
          overflowY: "auto",
          padding: 32,
          boxShadow: "0 24px 60px rgba(0,0,0,0.3)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 24,
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              background: "linear-gradient(135deg, #0672CB, #0460a9)",
              borderRadius: 12,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon.Zap size={24} color="#fff" />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 18, color: "#1e293b" }}>
              AI Case Analysis
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>
              Generated {formatDate(summary.generated_at)} · Model:{" "}
              {summary.model || "deepseek/deepseek-chat-v3.1"}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "#f1f5f9",
              border: "none",
              borderRadius: 8,
              width: 36,
              height: 36,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon.X size={18} />
          </button>
        </div>

        {/* Executive Summary */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "#0672CB",
              marginBottom: 8,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Icon.FileText size={16} /> Executive Summary
          </div>
          <div
            style={{
              background: "#f8fafc",
              borderRadius: 12,
              padding: 16,
              fontSize: 14,
              color: "#1e293b",
              lineHeight: 1.6,
              border: "1px solid #e2e8f0",
            }}
          >
            {summary.executive_summary || "No executive summary available"}
          </div>
        </div>

        {/* Key Risk Factors */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "#dc2626",
              marginBottom: 8,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Icon.AlertTriangle size={16} /> Key Risk Factors
          </div>
          <div
            style={{
              background: "#fef2f2",
              borderRadius: 12,
              padding: 16,
              border: "1px solid #fecaca",
            }}
          >
            {typeof summary.key_risk_factors === "string" ? (
              <div style={{ fontSize: 13, color: "#7f1d1d", lineHeight: 1.6 }}>
                {summary.key_risk_factors}
              </div>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 20, color: "#7f1d1d" }}>
                {summary.key_risk_factors?.map((factor, i) => (
                  <li key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                    {factor}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Two column layout for Behavioral and Cognitive Patterns */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
            marginBottom: 24,
          }}
        >
          <div>
            <div
              style={{
                fontWeight: 600,
                fontSize: 14,
                color: "#f59e0b",
                marginBottom: 8,
              }}
            >
              Behavioral Patterns
            </div>
            <div
              style={{
                background: "#fffbeb",
                borderRadius: 12,
                padding: 16,
                border: "1px solid #fcd34d",
                fontSize: 13,
                color: "#92400e",
                lineHeight: 1.6,
                minHeight: 100,
              }}
            >
              {summary.behavioral_patterns ||
                "No behavioral patterns identified"}
            </div>
          </div>
          <div>
            <div
              style={{
                fontWeight: 600,
                fontSize: 14,
                color: "#0460a9",
                marginBottom: 8,
              }}
            >
              Cognitive Patterns
            </div>
            <div
              style={{
                background: "#f5f3ff",
                borderRadius: 12,
                padding: 16,
                border: "1px solid #c4b5fd",
                fontSize: 13,
                color: "#5b21b6",
                lineHeight: 1.6,
                minHeight: 100,
              }}
            >
              {summary.cognitive_patterns || "No cognitive patterns identified"}
            </div>
          </div>
        </div>

        {/* Recommended Actions */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "#10b981",
              marginBottom: 8,
            }}
          >
            Recommended Actions
          </div>
          <div
            style={{
              background: "#d1fae5",
              borderRadius: 12,
              padding: 16,
              border: "1px solid #6ee7b7",
            }}
          >
            {typeof summary.recommended_actions === "string" ? (
              <div style={{ fontSize: 13, color: "#065f46", lineHeight: 1.6 }}>
                {summary.recommended_actions}
              </div>
            ) : (
              <ol style={{ margin: 0, paddingLeft: 20, color: "#065f46" }}>
                {summary.recommended_actions?.map((action, i) => (
                  <li key={i} style={{ fontSize: 13, marginBottom: 6 }}>
                    {action}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>

        {/* Supporting Evidence */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "#64748b",
              marginBottom: 8,
            }}
          >
            Supporting Evidence
          </div>
          <div
            style={{
              background: "#f8fafc",
              borderRadius: 12,
              padding: 16,
              border: "1px solid #e2e8f0",
              fontStyle: "italic",
              fontSize: 13,
              color: "#475569",
              lineHeight: 1.6,
            }}
          >
            {summary.supporting_evidence || "No supporting evidence available"}
          </div>
        </div>

        {/* Action Buttons */}
        <div
          style={{
            display: "flex",
            gap: 12,
            justifyContent: "flex-end",
            marginTop: 16,
          }}
        >
          <button
            onClick={onClose}
            style={{
              background: "#fff",
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: "10px 20px",
              fontSize: 13,
              fontWeight: 600,
              color: "#64748b",
              cursor: "pointer",
            }}
          >
            Close
          </button>
          {onGenerate && (
            <button
              onClick={() => {
                onGenerate();
                onClose();
              }}
              style={{
                background: "linear-gradient(135deg, #0672CB, #0460a9)",
                border: "none",
                borderRadius: 8,
                padding: "10px 20px",
                fontSize: 13,
                fontWeight: 600,
                color: "#fff",
                cursor: "pointer",
              }}
            >
              Generate New Summary
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
