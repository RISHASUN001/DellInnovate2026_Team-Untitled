import { useState, useEffect, useRef, useCallback } from "react";

// ─── DATA ────────────────────────────────────────────────────────────
const MOCK_CASES = [
  { id: 1, code: "YD-2026-0412", riskLevel: 3, category: "Bullying", platform: "Instagram", lastSignal: "2026-02-03 06:12 AM", status: "Active", assignedTo: "Sarah L.", assignedToMe: true, youth: { name: "Emma Chen", age: 15, avatar: "🧑‍🦱", handle: "@emma_chen_15", instagramUrl: "https://instagram.com/emma_chen_15" }, signals: ["Repeated negative comments in DMs detected", "Sentiment shift: positive → negative over 72h", "Keyword cluster: isolation, worthless, alone"], summary: "Adolescent showing linguistic markers consistent with peer-directed harassment. Sentiment analysis flagged a sharp downward shift over three days." },
  { id: 2, code: "YD-2026-0411", riskLevel: 5, category: "Self-Harm Ideation", platform: "Instagram", lastSignal: "2026-02-03 06:08 AM", status: "Escalated", assignedTo: "Sarah L.", assignedToMe: true, youth: { name: "Aiden Tan", age: 16, avatar: "👦", handle: "@aiden.tan", instagramUrl: "https://instagram.com/aiden.tan" }, signals: ["High-frequency distress keywords detected", "Cross-platform signal correlation with Reddit activity", "Temporal pattern: late-night clustering (11 PM – 2 AM)"], summary: "Multiple high-risk signals across platforms. Late-night activity pattern with elevated distress language. Flagged for urgent review." },
  { id: 3, code: "YD-2026-0409", riskLevel: 2, category: "Loneliness / Isolation", platform: "Instagram", lastSignal: "2026-02-03 00:15 AM", status: "Active", assignedTo: "Michael T.", assignedToMe: false, youth: { name: "Sophie Lim", age: 14, avatar: "👧", handle: "@sophie_lim", instagramUrl: "https://instagram.com/sophie_lim" }, signals: ["Decreased posting frequency over 30 days", "Shift to passive consumption behaviour", "Withdrawal from group interactions"], summary: "Gradual disengagement pattern noted. Posting frequency has declined significantly; interaction with peers has dropped." },
  { id: 4, code: "YD-2026-0408", riskLevel: 1, category: "Academic Stress", platform: "Instagram", lastSignal: "2026-02-02 18:40 PM", status: "Monitoring", assignedTo: "Rachel W.", assignedToMe: false, youth: { name: "Ryan Ng", age: 17, avatar: "🧑", handle: "@ryan.ng.17", instagramUrl: "https://instagram.com/ryan.ng.17" }, signals: ["Stress-related language uptick", "Mentions of deadlines and pressure"], summary: "Mild stress indicators around upcoming exams. Currently at watch level only." },
  { id: 5, code: "YD-2026-0405", riskLevel: 4, category: "Family Conflict", platform: "Instagram", lastSignal: "2026-02-03 04:50 AM", status: "Active", assignedTo: "Sarah L.", assignedToMe: true, youth: { name: "Maya Patel", age: 15, avatar: "👩", handle: "@maya.patel", instagramUrl: "https://instagram.com/maya.patel" }, signals: ["Escalation in emotional language over 48h", "Mentions of feeling unsafe", "Repeated mentions of 'leaving home'"], summary: "Elevated signals around domestic instability. Youth has expressed feeling unsafe. Requires careful, trauma-informed approach." },
  { id: 6, code: "YD-2026-0401", riskLevel: 2, category: "Bullying", platform: "Instagram", lastSignal: "2026-02-01 22:00 PM", status: "Pending", assignedTo: "—", assignedToMe: false, youth: { name: "Lucas Wong", age: 13, avatar: "🧒", handle: "@lucas_w", instagramUrl: "https://instagram.com/lucas_w" }, signals: ["Repetitive negative peer interactions flagged", "Keyword cluster: excluded, mocked"], summary: "Early-stage bullying indicators. Not yet assigned to a helper." },
  { id: 7, code: "YD-2026-0398", riskLevel: 3, category: "Cyberbullying", platform: "Instagram", lastSignal: "2026-02-02 10:30 AM", status: "Active", assignedTo: "Michael T.", assignedToMe: false, youth: { name: "Chloe Teo", age: 16, avatar: "👩‍🦰", handle: "@chloe.teo", instagramUrl: "https://instagram.com/chloe.teo" }, signals: ["Comment-thread toxicity score elevated", "Target account activity dip post-incident"], summary: "Toxic comment cluster targeting youth content. AI flagged cross-video pattern." },
  { id: 8, code: "YD-2026-0415", riskLevel: 5, category: "Self-Harm Ideation", platform: "Instagram", lastSignal: "2026-02-03 07:30 AM", status: "Active", assignedTo: "Sarah L.", assignedToMe: true, youth: { name: "Daniel Lee", age: 15, avatar: "🧑‍🦲", handle: "@daniel_lee_sg", instagramUrl: "https://instagram.com/daniel_lee_sg" }, signals: ["Direct mentions of self-harm methods", "Farewell messages to friends detected", "Profile bio changed to concerning content"], summary: "Critical risk signals detected. Multiple explicit references to self-harm. Immediate intervention required." },
  { id: 9, code: "YD-2026-0413", riskLevel: 4, category: "Cyberbullying", platform: "Instagram", lastSignal: "2026-02-03 05:45 AM", status: "Active", assignedTo: "Michael T.", assignedToMe: false, youth: { name: "Priya Kumar", age: 14, avatar: "👧🏾", handle: "@priya.k.14", instagramUrl: "https://instagram.com/priya.k.14" }, signals: ["Targeted harassment from multiple accounts", "Doxxing attempts detected", "Coordinated negative comments across posts"], summary: "Organized cyberbullying campaign identified. Multiple perpetrators coordinating attacks. Youth has stopped posting." },
  { id: 10, code: "YD-2026-0410", riskLevel: 3, category: "Family Conflict", platform: "Instagram", lastSignal: "2026-02-03 02:15 AM", status: "Active", assignedTo: "Rachel W.", assignedToMe: false, youth: { name: "Ethan Goh", age: 16, avatar: "🧑‍🎓", handle: "@ethan_goh", instagramUrl: "https://instagram.com/ethan_goh" }, signals: ["Frequent mentions of family arguments", "Posts about 'wanting to run away'", "Late-night emotional venting posts"], summary: "Ongoing family tension. Youth expressing desire to leave home. Needs family counseling referral." },
  { id: 11, code: "YD-2026-0407", riskLevel: 2, category: "Academic Stress", platform: "Instagram", lastSignal: "2026-02-02 23:30 PM", status: "Monitoring", assignedTo: "—", assignedToMe: false, youth: { name: "Isabella Chan", age: 17, avatar: "👩‍💼", handle: "@bella.chan", instagramUrl: "https://instagram.com/bella.chan" }, signals: ["Increased stress language around exams", "Sleep deprivation mentions", "Performance anxiety indicators"], summary: "Academic pressure mounting as exams approach. Monitoring for escalation signs." },
  { id: 12, code: "YD-2026-0406", riskLevel: 3, category: "Loneliness / Isolation", platform: "Instagram", lastSignal: "2026-02-02 20:10 PM", status: "Monitoring", assignedTo: "—", assignedToMe: false, youth: { name: "Marcus Loh", age: 15, avatar: "🧑‍🦳", handle: "@marcus.loh", instagramUrl: "https://instagram.com/marcus.loh" }, signals: ["Zero interaction with peers in 2 weeks", "Stories about feeling invisible", "Posts about not being invited to events"], summary: "Social isolation pattern. Youth feels excluded from peer groups. Low engagement on posts." },
  { id: 13, code: "YD-2026-0404", riskLevel: 4, category: "Bullying", platform: "Instagram", lastSignal: "2026-02-02 16:45 PM", status: "Active", assignedTo: "Michael T.", assignedToMe: false, youth: { name: "Zara Ahmed", age: 14, avatar: "👧🏽", handle: "@zara.ahmed", instagramUrl: "https://instagram.com/zara.ahmed" }, signals: ["Physical threats mentioned in comments", "Screenshots of threatening DMs shared", "Fear-related language in recent posts"], summary: "Bullying escalated to threats of physical harm. School coordination needed urgently." },
  { id: 14, code: "YD-2026-0403", riskLevel: 1, category: "Academic Stress", platform: "Instagram", lastSignal: "2026-02-02 14:20 PM", status: "Monitoring", assignedTo: "—", assignedToMe: false, youth: { name: "Oliver Tan", age: 16, avatar: "🧑‍🔬", handle: "@oliver.tan.sg", instagramUrl: "https://instagram.com/oliver.tan.sg" }, signals: ["Mild complaints about homework load", "Time management concerns"], summary: "Normal academic stress levels. No intervention needed at this time." },
  { id: 15, code: "YD-2026-0402", riskLevel: 2, category: "Loneliness / Isolation", platform: "Instagram", lastSignal: "2026-02-02 11:30 AM", status: "Monitoring", assignedTo: "—", assignedToMe: false, youth: { name: "Amelia Koh", age: 13, avatar: "👧🏻", handle: "@amelia.koh", instagramUrl: "https://instagram.com/amelia.koh" }, signals: ["Reduced friend interactions", "Posts about feeling left out", "Declining social activity"], summary: "Early signs of social withdrawal. Monitoring for further decline." },
];

const RISK_COLORS = { 1: { bg: "#d1fae5", text: "#065f46", label: "Low" }, 2: { bg: "#dbeafe", text: "#1e40af", label: "Low-Med" }, 3: { bg: "#fef3c7", text: "#92400e", label: "Medium" }, 4: { bg: "#ffedd5", text: "#c2410c", label: "High" }, 5: { bg: "#fee2e2", text: "#991b1b", label: "Critical" } };

const PRESET_QUESTIONS = [
  { icon: "🛡️", label: "How to approach a bullying case", q: "How should I approach a case involving bullying? What's the recommended first step?" },
  { icon: "✉️", label: "Recommended outreach messages", q: "Can you suggest recommended outreach message templates I can adapt for initial contact?" },
  { icon: "📈", label: "Escalation criteria", q: "What are the escalation criteria? When should I escalate a case?" },
  { icon: "📅", label: "Follow-up timelines", q: "What are the recommended follow-up timelines for active cases?" },
  { icon: "📚", label: "Resources to share", q: "What resources and referral links are available to share with youth or their families?" },
];

const CHATBOT_RESPONSES = {
  default: "Thank you for your question. Based on SCS protocols, I recommend reviewing the case signals carefully before deciding on next steps. All outreach decisions are yours — I'm here to guide, not to act. Would you like help with a specific aspect of this case?",
  bullying: "**Approaching Bullying Cases:**\n\n1. **Assess severity** — Is it a single incident or a repeated pattern? Check the AI signals for frequency and escalation.\n2. **Do not confront the perpetrator directly** — Focus on the youth's wellbeing first.\n3. **Reach out with warmth** — Use a non-judgmental, empathetic tone. Acknowledge their feelings before offering support.\n4. **Document everything** — Use the checklist to note your outreach attempt and response.\n5. **Involve school or platform** — If the bullying is on a school platform, coordinate with SCS school liaison.\n\n⚠️ *Remember: You decide whether and how to reach out. AI assists prioritisation only.*",
  outreach: "**Recommended Outreach Message Templates:**\n\n📝 *Template A (General):*\n\"Hi [Name], I'm [Your Name] from YOUTH(TH)CARE. I wanted to check in with you. You don't have to share anything you're not comfortable with — I'm just here to listen if you need.\"\n\n📝 *Template B (After a difficult event):*\n\"I heard things have been a bit tough lately. Please know there are people who care, and support is available whenever you're ready.\"\n\n📝 *Template C (Follow-up):*\n\"Just wanted to let you know I'm still here. No pressure — take your time. 😊\"\n\n⚠️ *Always personalise these. You know the context best.*",
  escalation: "**Escalation Criteria (SCS Protocol):**\n\nEscalate a case if **any** of the following apply:\n- 🔴 Youth expresses intent to self-harm or harm others\n- 🔴 Youth mentions feeling unsafe at home\n- 🟠 Risk score is 4 or above AND outreach has not received a response within 48 hours\n- 🟠 Multiple high-risk signals across different platforms\n- 🟡 Youth is under 14 and the case involves any form of abuse\n\n**To escalate:** Use the 'Escalation considered' checklist item, add your notes, and notify your team lead.\n\n⚠️ *When in doubt, escalate. Better safe than sorry.*",
  followup: "**Follow-Up Timelines (SCS Protocol):**\n\n| Risk Level | First Outreach | Follow-Up 1 | Follow-Up 2 | Review |\n|---|---|---|---|---|\n| Critical (5) | Within 2 hours | 24 hours | 48 hours | 72 hours |\n| High (4) | Within 6 hours | 48 hours | 72 hours | 1 week |\n| Medium (3) | Within 24 hours | 3 days | 1 week | 2 weeks |\n| Low-Med (2) | Within 48 hours | 1 week | 2 weeks | 1 month |\n| Low (1) | Within 1 week | 2 weeks | 1 month | Quarterly |\n\n⚠️ *These are guidelines. Adjust based on the youth's response and comfort level.*",
  resources: "**Resources & Referrals Available:**\n\n🏥 **Samaritans of Singapore** — 1800-221-4444 (24/7)\n🧠 **Childcare Link** — counselling & mental health support\n🏫 **School Liaison Programme** — coordinate with school counsellors\n📱 **Youthline (Hong Kong, for cross-regional cases)** — 2382 0000\n🌐 **SCS Online Support Portal** — secure messaging platform for youth\n📋 **Community Mental Health Teams** — for home visits if needed\n\n⚠️ *Always check with your team lead before sharing external resources. Ensure the youth and family consent.*",
};

function getChatbotResponse(input, attachedCase) {
  const lower = input.toLowerCase();
  let key = "default";
  if (lower.includes("bully")) key = "bullying";
  else if (lower.includes("outreach") || lower.includes("message") || lower.includes("template")) key = "outreach";
  else if (lower.includes("escalat")) key = "escalation";
  else if (lower.includes("follow")) key = "followup";
  else if (lower.includes("resource") || lower.includes("referral")) key = "resources";

  let prefix = "";
  if (attachedCase) prefix = `📎 *Reviewing case ${attachedCase.code} (${attachedCase.category}, Risk ${attachedCase.riskLevel}/5):*\n\n`;
  return prefix + CHATBOT_RESPONSES[key];
}

// ─── ONBOARDING STEPS ────────────────────────────────────────────────
const ONBOARDING_STEPS = [
  { title: "Welcome to SCS Youth Helper Dashboard", desc: "This guided walkthrough will teach you how to use the dashboard. All decisions about youth outreach remain yours — AI is here only to help you prioritise and guide.", target: "hero-welcome", img: "🏠", step: 1, total: 11 },
  { title: "1. The All Cases Dashboard", desc: "This is your global view organized by category columns. Each column shows cases of the same type (Self-Harm, Bullying, etc.), ordered by priority (highest risk first). Each card shows risk level (colour-coded 1–5), platform, last signal time, status, and assigned helper. The top-right shows when data was last ingested (every 6 hours) for privacy and platform compliance. Original social media content is never stored.", target: "tab-all", img: "📊", step: 2, total: 11 },
  { title: "2. Understanding Risk Levels", desc: "Risk levels range from 1 (Low - green) to 5 (Critical - red). These color-coded badges help you quickly identify priority cases. Critical (5) requires immediate attention within 2 hours, while Low (1) can be monitored weekly. The AI calculates risk based on language patterns, frequency, and sentiment shifts.", target: "risk-badge", img: "🎯", step: 3, total: 11, highlight: "risk-badge" },
  { title: "3. Case Status Indicators", desc: "Status badges show the current state: Active (needs attention), Escalated (flagged for urgent review), Monitoring (being watched), or Pending (unassigned). Escalated cases (red badge) require immediate team lead notification and appear at the top of your queue.", target: "status-badge", img: "🏷️", step: 4, total: 11, highlight: "status-badge" },
  { title: "4. Assigning & Accessing Cases", desc: "Unassigned cases show '—' in the helper column. When a case is assigned to you, it appears in your 'Assigned to Me' tab with full details. Summary-only visibility (All Cases) vs. full access (Assigned to Me) is a key privacy boundary.", target: "tab-assigned", img: "🔐", step: 5, total: 11 },
  { title: "5. Your Primary Workspace", desc: "The 'Assigned to Me' tab is where you'll spend most of your time. Here you can see your cases and open them for detailed review. Click any case card to begin.", target: "workspace-panel", img: "💼", step: 6, total: 11 },
  { title: "6. Drag & Drop Reordering", desc: "In the 'Assigned to Me' tab, you can reorder cases by dragging and dropping them, just like in Jira. This helps you organize your workload according to your own priorities. The order you set is saved for your use.", target: "workspace-panel", img: "🔄", step: 7, total: 11 },
  { title: "7. Youth Profile & Contact Info", desc: "Each case shows the youth's profile with their name, age, Instagram handle, and avatar. This helps you understand who you're supporting. The profile includes all necessary contact information while maintaining privacy protocols.", target: "youth-profile", img: "👤", step: 8, total: 11, highlight: "youth-profile" },
  { title: "8. Reach Out Button", desc: "The 'Reach Out via Instagram' button lets you initiate contact with the youth. Click this when you're ready to make contact after reviewing the case. IMPORTANT: Always review SCS outreach protocols and use trauma-informed language before reaching out.", target: "reach-out-button", img: "📩", step: 9, total: 11, highlight: "reach-out-button" },
  { title: "9. AI Signals & Risk Assessment", desc: "AI signals explain why a case was flagged. Each numbered signal shows specific patterns detected: distress keywords, sentiment shifts, temporal patterns, or behavioral changes. These are insights to guide your decision - you determine the appropriate action.", target: "case-detail-area", img: "🔍", step: 10, total: 11 },
  { title: "10. The Checklist & Comments", desc: "Use the checklist to track mandatory steps: outreach attempted, response received, follow-up scheduled, escalation considered, and case closed. You can add comments and custom checklist items. Only you can see your edits.", target: "checklist-panel", img: "✅", step: 11, total: 11 },
  { title: "11. The Recommendation Chatbot", desc: "The chatbot at the bottom-right offers guidance based on SCS protocols. Use the 📎 icon to attach one of your assigned cases for context. Try the quick-action preset buttons for common questions. Remember: AI guides, you decide.", target: "chatbot-area", img: "💬", step: 12, total: 11 },
];

// ─── COMPONENTS ──────────────────────────────────────────────────────

function RiskBadge({ level }) {
  const c = RISK_COLORS[level];
  return <span style={{ background: c.bg, color: c.text, padding: "3px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600, whiteSpace: "nowrap" }}>{c.label} ({level})</span>;
}

function StatusBadge({ status }) {
  const map = { Active: ["#e0e7ff", "#3730a3"], Escalated: ["#fee2e2", "#991b1b"], Monitoring: ["#f3f4f6", "#4b5563"], Pending: ["#fef9c3", "#854d0e"] };
  const [bg, txt] = map[status] || ["#f3f4f6", "#4b5563"];
  return <span style={{ background: bg, color: txt, padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600 }}>{status}</span>;
}

function DataFreshnessIndicator({ highlight }) {
  return (
    <div id="freshness-indicator" style={{ display: "flex", alignItems: "center", gap: 10, background: highlight ? "#fef3c7" : "rgba(255,255,255,0.08)", border: highlight ? "2px solid #f59e0b" : "1px solid rgba(255,255,255,0.15)", borderRadius: 10, padding: "8px 14px", transition: "all 0.4s" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 14 }}>🔄</span>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: highlight ? "#92400e" : "#cbd5e1", letterSpacing: "0.5px" }}>LAST INGESTION</div>
          <div style={{ fontSize: 12, color: highlight ? "#78350f" : "#94a3b8" }}>Today, 06:12 AM · Next in ~3h 48m</div>
        </div>
      </div>
      <div style={{ width: 1, height: 30, background: highlight ? "#f59e0b" : "rgba(255,255,255,0.2)", margin: "0 4px" }}></div>
      <div style={{ fontSize: 10, color: highlight ? "#92400e" : "#94a3b8", maxWidth: 140, lineHeight: 1.35 }}>
        Data refreshes every <strong>6 hours</strong> for privacy & platform compliance. Original content is <strong>not stored</strong>.
      </div>
    </div>
  );
}

function CaseCard({ c, onClick, highlight, isAssignedView }) {
  return (
    <div id={`case-card-${c.id}`} onClick={() => onClick(c)} style={{ background: "#fff", borderRadius: 12, border: highlight ? "2px solid #6366f1" : "1px solid #e2e8f0", padding: "14px 16px", cursor: "pointer", transition: "all 0.2s", boxShadow: highlight ? "0 0 0 3px rgba(99,102,241,0.25)" : "0 1px 3px rgba(0,0,0,0.06)", position: "relative" }} onMouseEnter={e => e.currentTarget.style.boxShadow = "0 4px 14px rgba(0,0,0,0.1)"} onMouseLeave={e => e.currentTarget.style.boxShadow = highlight ? "0 0 0 3px rgba(99,102,241,0.25)" : "0 1px 3px rgba(0,0,0,0.06)"}>
      {!isAssignedView && c.assignedToMe && <div style={{ position: "absolute", top: 8, right: 8, background: "#6366f1", color: "#fff", fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 10 }}>MINE</div>}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontWeight: 700, fontSize: 13, color: "#1e293b" }}>{c.code}</span>
        <RiskBadge level={c.riskLevel} />
        <StatusBadge status={c.status} />
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12, color: "#64748b", marginBottom: 6 }}>
        <span>🏷️ {c.category}</span>
        <span>📱 {c.platform}</span>
        <span>🕐 {c.lastSignal}</span>
        <span>👤 {c.assignedTo}</span>
      </div>
      <div style={{ fontSize: 12, color: "#475569", lineHeight: 1.45, borderTop: "1px solid #f1f5f9", paddingTop: 6, marginTop: 4 }}>{c.summary}</div>
    </div>
  );
}

// ─── MAIN APP ────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState("all");
  const [selectedCase, setSelectedCase] = useState(null);
  const [onboardingStep, setOnboardingStep] = useState(0); // 0 = show welcome modal
  const [onboardingActive, setOnboardingActive] = useState(true);
  const [onboardingDone, setOnboardingDone] = useState(false);
  const [showChatbot, setShowChatbot] = useState(false);
  const [showHelpMenu, setShowHelpMenu] = useState(false);
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [assignedCasesOrder, setAssignedCasesOrder] = useState(MOCK_CASES.filter(c => c.assignedToMe).map(c => c.id));

  const myAssignedCases = assignedCasesOrder.map(id => MOCK_CASES.find(c => c.id === id)).filter(Boolean);
  
  // Group cases by category for All Cases view
  const casesByCategory = MOCK_CASES.reduce((acc, c) => {
    if (!acc[c.category]) acc[c.category] = [];
    acc[c.category].push(c);
    return acc;
  }, {});
  
  // Sort each category by priority (risk level descending)
  Object.keys(casesByCategory).forEach(category => {
    casesByCategory[category].sort((a, b) => b.riskLevel - a.riskLevel);
  });
  
  // Get sorted categories (by highest risk level in each category)
  const sortedCategories = Object.keys(casesByCategory).sort((a, b) => {
    const maxRiskA = Math.max(...casesByCategory[a].map(c => c.riskLevel));
    const maxRiskB = Math.max(...casesByCategory[b].map(c => c.riskLevel));
    return maxRiskB - maxRiskA;
  });
  
  // Drag and drop handlers
  const handleDragStart = (index) => {
    setDraggedIndex(index);
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
  };

  // Auto-advance onboarding context
  useEffect(() => {
    if (!onboardingActive || onboardingDone) return;
    if (onboardingStep === 1) setActiveTab("all");
    if (onboardingStep === 2) setActiveTab("all");
    if (onboardingStep === 3) { setActiveTab("all"); setSelectedCase(MOCK_CASES[1]); } // Show case to highlight risk badge
    if (onboardingStep === 4) { setActiveTab("all"); setSelectedCase(MOCK_CASES[1]); } // Show case to highlight status badge
    if (onboardingStep === 5) setActiveTab("assigned");
    if (onboardingStep === 6) setActiveTab("assigned");
    if (onboardingStep === 7) setActiveTab("assigned");
    if (onboardingStep === 8) { setActiveTab("assigned"); setSelectedCase(myAssignedCases[0]); } // Youth profile
    if (onboardingStep === 9) { setActiveTab("assigned"); setSelectedCase(myAssignedCases[0]); } // Reach out button
    if (onboardingStep === 10) { setActiveTab("assigned"); setSelectedCase(myAssignedCases[0]); } // AI signals
    if (onboardingStep === 11) { setActiveTab("assigned"); setSelectedCase(myAssignedCases[0]); } // Checklist
    if (onboardingStep === 12) { setSelectedCase(myAssignedCases[0]); setShowChatbot(true); } // Chatbot
  }, [onboardingStep]);

  const highlightTarget = onboardingActive && !onboardingDone ? ONBOARDING_STEPS[onboardingStep]?.highlight || ONBOARDING_STEPS[onboardingStep]?.target : null;

  return (
    <div style={{ fontFamily: "'Segoe UI', system-ui, sans-serif", background: "#f0f4f8", minHeight: "100vh", display: "flex", flexDirection: "column", fontSize: 14, color: "#1e293b", position: "relative", overflow: "hidden" }}>
      {/* ── TOP NAV ── */}
      <nav style={{ background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)", color: "#fff", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, position: "relative", zIndex: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>🌟</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: "0.3px" }}>Singapore Children's Society</div>
            <div style={{ fontSize: 10, color: "#94a3b8", letterSpacing: "1.2px", textTransform: "uppercase" }}>YOUTH<sup>TH</sup>CARE</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <DataFreshnessIndicator highlight={highlightTarget === "tab-all"} />
          <div style={{ position: "relative" }}>
            <button onClick={() => setShowHelpMenu(!showHelpMenu)} style={{ background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)", color: "#fff", borderRadius: 8, padding: "6px 14px", cursor: "pointer", fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>❓ Help</button>
            {showHelpMenu && (
              <div style={{ position: "absolute", top: "calc(100% + 6px)", right: 0, background: "#fff", borderRadius: 12, boxShadow: "0 8px 30px rgba(0,0,0,0.18)", width: 220, zIndex: 100, overflow: "hidden" }}>
                <div style={{ padding: "6px 0" }}>
                  <button onClick={() => { setOnboardingActive(true); setOnboardingDone(false); setOnboardingStep(0); setShowHelpMenu(false); }} style={{ width: "100%", textAlign: "left", background: "none", border: "none", padding: "10px 16px", cursor: "pointer", fontSize: 13, color: "#1e293b", display: "flex", alignItems: "center", gap: 10 }} onMouseEnter={e => e.currentTarget.style.background = "#f1f5f9"} onMouseLeave={e => e.currentTarget.style.background = "none"}>🎓 Run Onboarding Walkthrough</button>
                  <button onClick={() => { setShowHelpMenu(false); }} style={{ width: "100%", textAlign: "left", background: "none", border: "none", padding: "10px 16px", cursor: "pointer", fontSize: 13, color: "#1e293b", display: "flex", alignItems: "center", gap: 10 }} onMouseEnter={e => e.currentTarget.style.background = "#f1f5f9"} onMouseLeave={e => e.currentTarget.style.background = "none"}>📖 User Guide (PDF)</button>
                  <button onClick={() => { setShowHelpMenu(false); }} style={{ width: "100%", textAlign: "left", background: "none", border: "none", padding: "10px 16px", cursor: "pointer", fontSize: 13, color: "#1e293b", display: "flex", alignItems: "center", gap: 10 }} onMouseEnter={e => e.currentTarget.style.background = "#f1f5f9"} onMouseLeave={e => e.currentTarget.style.background = "none"}>📧 Contact Support</button>
                </div>
              </div>
            )}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, background: "rgba(255,255,255,0.08)", padding: "5px 12px", borderRadius: 20, border: "1px solid rgba(255,255,255,0.15)" }}>
            <div style={{ width: 28, height: 28, borderRadius: "50%", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13 }}>SL</div>
            <span style={{ fontSize: 13 }}>Sarah L.</span>
          </div>
        </div>
      </nav>

      {/* ── PRIVACY BANNER ── */}
      <div style={{ background: "#eef2ff", borderBottom: "1px solid #c7d2fe", padding: "6px 24px", fontSize: 11.5, color: "#4338ca", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <span>🔒</span> <strong>Privacy Notice:</strong> This dashboard displays AI-generated risk assessments only. Original social media content is never stored or displayed. All outreach decisions are made by you. Your edits and interactions are private to your account.
      </div>

      {/* ── ONBOARDING WELCOME MODAL ── */}
      {onboardingActive && !onboardingDone && onboardingStep === 0 && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.7)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ background: "#fff", borderRadius: 20, maxWidth: 520, width: "90%", padding: 40, textAlign: "center", boxShadow: "0 24px 60px rgba(0,0,0,0.3)" }}>
            <div style={{ fontSize: 52, marginBottom: 12 }}>🎓</div>
            <h2 style={{ margin: "0 0 8px", fontSize: 22, color: "#1e293b" }}>Welcome to the SCS Youth Helper Dashboard</h2>
            <p style={{ margin: "0 0 8px", color: "#64748b", fontSize: 14, lineHeight: 1.6 }}>This short walkthrough will guide you through every feature — from viewing cases to using the recommendation chatbot.</p>
            <p style={{ margin: "0 0 24px", color: "#6366f1", fontSize: 13, fontWeight: 600 }}>AI assists prioritisation and guidance. All outreach decisions are yours.</p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button onClick={() => setOnboardingStep(1)} style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", border: "none", borderRadius: 10, padding: "11px 32px", fontSize: 14, fontWeight: 600, cursor: "pointer", boxShadow: "0 4px 14px rgba(99,102,241,0.4)" }}>Start Walkthrough →</button>
              <button onClick={() => { setOnboardingActive(false); setOnboardingDone(true); }} style={{ background: "#f1f5f9", color: "#64748b", border: "none", borderRadius: 10, padding: "11px 22px", fontSize: 13, cursor: "pointer" }}>Skip for now</button>
            </div>
          </div>
        </div>
      )}

      {/* ── ONBOARDING STEP OVERLAY ── */}
      {onboardingActive && !onboardingDone && onboardingStep >= 1 && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.55)", zIndex: 200, pointerEvents: "none" }}></div>
      )}
      {onboardingActive && !onboardingDone && onboardingStep >= 1 && (() => {
        const step = ONBOARDING_STEPS[onboardingStep];
        if (!step) return null;
        const posMap = {
          "tab-all": { top: 160, left: "50%", transform: "translateX(-50%)" },
          "risk-badge": { top: 200, right: 20, left: "auto", transform: "none" },
          "status-badge": { top: 200, right: 20, left: "auto", transform: "none" },
          "tab-assigned": { top: 160, left: "50%", transform: "translateX(-50%)" },
          "workspace-panel": { top: 240, left: "calc(50% - 160px)" },
          "youth-profile": { top: 180, right: 20, left: "auto", transform: "none" },
          "reach-out-button": { top: 240, right: 20, left: "auto", transform: "none" },
          "case-detail-area": { top: 240, right: 20, left: "auto", transform: "none" },
          "checklist-panel": { top: 380, right: 20, left: "auto", transform: "none" },
          "chatbot-area": { bottom: 100, right: 20, left: "auto", top: "auto", transform: "none" },
        };
        const pos = posMap[step.target] || { top: 200, left: "50%", transform: "translateX(-50%)" };
        return (
          <div style={{ position: "fixed", ...pos, zIndex: 201, pointerEvents: "auto", width: 380, background: "#fff", borderRadius: 16, boxShadow: "0 16px 48px rgba(0,0,0,0.28)", overflow: "hidden" }}>
            <div style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ color: "#fff", fontSize: 13, fontWeight: 600 }}>Step {step.step} of {step.total}</span>
              <button onClick={() => { setOnboardingActive(false); setOnboardingDone(true); }} style={{ background: "rgba(255,255,255,0.2)", border: "none", color: "#fff", borderRadius: 6, width: 24, height: 24, cursor: "pointer", fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
            </div>
            <div style={{ padding: "18px 20px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
                <div style={{ fontSize: 28 }}>{step.img}</div>
                <h3 style={{ margin: 0, fontSize: 15, color: "#1e293b", lineHeight: 1.3 }}>{step.title}</h3>
              </div>
              <p style={{ margin: "0 0 16px", fontSize: 13, color: "#64748b", lineHeight: 1.55 }}>{step.desc}</p>
              {/* Visual example box */}
              <div style={{ background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: 10, padding: "10px 14px", marginBottom: 16 }}>
                <div style={{ fontSize: 10, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 4 }}>👁️ Look for</div>
                <div style={{ fontSize: 12, color: "#475569" }}>
                  {step.step === 1 && "The dashboard header and privacy banner at the top."}
                  {step.step === 2 && "Cases organized into category columns (Self-Harm, Bullying, etc.), with highest priority cases at the top of each column. Risk badges (green → red) and the 🔄 data freshness indicator top-right."}
                  {step.step === 3 && "The highlighted RISK BADGE showing the color-coded risk level (1-5). Notice how Critical (5) is red, Medium (3) is yellow, and Low (1) is green."}
                  {step.step === 4 && "The highlighted STATUS BADGE next to the risk level. Active = blue, Escalated = red, Monitoring = gray, Pending = yellow."}
                  {step.step === 5 && "The 'Assigned to Me' tab — cases here show a 'MINE' badge in All Cases view."}
                  {step.step === 6 && "Your assigned case cards in the left panel. Click one to open it."}
                  {step.step === 7 && "Grab any case card and drag it up or down to reorder. Your custom order will be saved."}
                  {step.step === 8 && "The highlighted YOUTH PROFILE card showing the person's avatar, name, age, and Instagram handle. This is who you'll be supporting."}
                  {step.step === 9 && "The highlighted 'REACH OUT VIA INSTAGRAM' button. Click this when ready to initiate contact. Always review protocols first!"}
                  {step.step === 10 && "The AI signals section explaining why this case was flagged. Each numbered signal shows specific patterns detected."}
                  {step.step === 11 && "The checklist with mandatory items and the + button to add custom items and comments."}
                </div>
              </div>
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                {onboardingStep > 1 && <button onClick={() => setOnboardingStep(s => s - 1)} style={{ background: "#f1f5f9", color: "#64748b", border: "none", borderRadius: 8, padding: "8px 18px", fontSize: 13, cursor: "pointer" }}>← Back</button>}
                {onboardingStep < 11 ? (
                  <button onClick={() => setOnboardingStep(s => s + 1)} style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", border: "none", borderRadius: 8, padding: "8px 22px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>Next →</button>
                ) : (
                  <button onClick={() => { setOnboardingActive(false); setOnboardingDone(true); }} style={{ background: "linear-gradient(135deg, #10b981, #059669)", color: "#fff", border: "none", borderRadius: 8, padding: "8px 22px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>✓ Done</button>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── MAIN BODY ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* ── LEFT: TAB NAVIGATION + CASE LIST ── */}
        <div id="workspace-panel" style={{ width: selectedCase ? 380 : "100%", minWidth: selectedCase ? 340 : undefined, maxWidth: selectedCase ? 420 : undefined, background: "#fff", borderRight: "1px solid #e2e8f0", display: "flex", flexDirection: "column", overflow: "hidden", transition: "width 0.3s ease" }}>
          {/* Tabs */}
          <div id="tab-all" style={{ display: "flex", borderBottom: "1px solid #e2e8f0", background: highlightTarget === "tab-all" || highlightTarget === "tab-assigned" ? "#eef2ff" : "#fff", transition: "background 0.3s", border: highlightTarget === "tab-all" || highlightTarget === "tab-assigned" ? "2px solid #6366f1" : "none", borderBottom: "1px solid #e2e8f0", borderRadius: "0 0 0 0" }}>
            <button onClick={() => { setActiveTab("all"); setSelectedCase(null); }} style={{ flex: 1, padding: "13px 0", background: "none", border: "none", cursor: "pointer", fontSize: 13, fontWeight: activeTab === "all" ? 700 : 500, color: activeTab === "all" ? "#6366f1" : "#64748b", borderBottom: activeTab === "all" ? "3px solid #6366f1" : "3px solid transparent", transition: "all 0.2s" }}>
              📋 All Cases <span style={{ background: "#e0e7ff", color: "#4338ca", borderRadius: 10, padding: "1px 8px", fontSize: 11, marginLeft: 4 }}>{MOCK_CASES.length}</span>
            </button>
            <button id="tab-assigned" onClick={() => { setActiveTab("assigned"); setSelectedCase(null); }} style={{ flex: 1, padding: "13px 0", background: "none", border: "none", cursor: "pointer", fontSize: 13, fontWeight: activeTab === "assigned" ? 700 : 500, color: activeTab === "assigned" ? "#6366f1" : "#64748b", borderBottom: activeTab === "assigned" ? "3px solid #6366f1" : "3px solid transparent", transition: "all 0.2s" }}>
              👤 Assigned to Me <span style={{ background: "#ddd6fe", color: "#5b21b6", borderRadius: 10, padding: "1px 8px", fontSize: 11, marginLeft: 4 }}>{myAssignedCases.length}</span>
            </button>
          </div>
          {/* Case list */}
          {activeTab === "all" ? (
            // Category columns view for All Cases
            <div style={{ flex: 1, overflowY: "auto", overflowX: "auto", padding: 12, display: "flex", gap: 12 }}>
              {sortedCategories.map(category => (
                <div key={category} style={{ minWidth: 280, maxWidth: 320, flex: "0 0 auto", display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ position: "sticky", top: 0, background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", padding: "8px 12px", borderRadius: 10, fontWeight: 700, fontSize: 13, display: "flex", alignItems: "center", justifyContent: "space-between", zIndex: 1 }}>
                    <span>{category}</span>
                    <span style={{ background: "rgba(255,255,255,0.2)", borderRadius: 12, padding: "2px 8px", fontSize: 11 }}>{casesByCategory[category].length}</span>
                  </div>
                  {casesByCategory[category].map(c => (
                    <CaseCard key={c.id} c={c} isAssignedView={false} highlight={highlightTarget === "workspace-panel" && c.id === myAssignedCases[0]?.id} onClick={c => { if (!c.assignedToMe) return alert("📌 This case is not assigned to you. Only summary view is available.\\n\\nTo access full details, the case must be assigned to you."); setSelectedCase(c); }} />
                  ))}
                </div>
              ))}
            </div>
          ) : (
            // List view with drag-and-drop for Assigned to Me
            <div style={{ flex: 1, overflowY: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
              {myAssignedCases.map((c, index) => (
                <div 
                  key={c.id} 
                  draggable 
                  onDragStart={() => handleDragStart(index)}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDragEnd={handleDragEnd}
                  style={{ 
                    cursor: "move",
                    opacity: draggedIndex === index ? 0.5 : 1,
                    transition: "opacity 0.2s"
                  }}
                >
                  <CaseCard c={c} isAssignedView={true} highlight={highlightTarget === "workspace-panel" && c.id === myAssignedCases[0]?.id} onClick={c => setSelectedCase(c)} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── RIGHT: CASE DETAIL PANEL ── */}
        {selectedCase && (
          <div id="case-detail-area" style={{ flex: 1, display: "flex", flexDirection: "column", overflowY: "auto", background: "#f0f4f8", position: "relative" }}>
            {/* Case header */}
            <div style={{ background: "#fff", borderBottom: "1px solid #e2e8f0", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <button onClick={() => setSelectedCase(null)} style={{ background: "#f1f5f9", border: "none", borderRadius: 8, width: 34, height: 34, cursor: "pointer", fontSize: 18, color: "#64748b", display: "flex", alignItems: "center", justifyContent: "center" }}>←</button>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontWeight: 700, fontSize: 16 }}>{selectedCase.code}</span>
                    <RiskBadge level={selectedCase.riskLevel} />
                    <StatusBadge status={selectedCase.status} />
                  </div>
                  <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>📱 {selectedCase.platform} · 🕐 Last signal: {selectedCase.lastSignal}</div>
                </div>
              </div>
              <div style={{ background: "#fef3c7", border: "1px solid #f59e0b", borderRadius: 8, padding: "6px 12px", fontSize: 11, color: "#92400e", display: "flex", alignItems: "center", gap: 6 }}>🔒 Your edits are private</div>
            </div>

            {/* Detail content */}
            <div style={{ flex: 1, display: "flex", gap: 0, overflow: "hidden" }}>
              {/* Left col: AI signals + summary */}
              <div style={{ flex: 1, padding: 20, overflowY: "auto" }}>
                {/* Privacy disclaimer */}
                <div style={{ background: "#eef2ff", border: "1px solid #c7d2fe", borderRadius: 10, padding: "10px 14px", marginBottom: 16, display: "flex", gap: 10, alignItems: "flex-start" }}>
                  <span style={{ fontSize: 18, flexShrink: 0 }}>🛡️</span>
                  <div style={{ fontSize: 12, color: "#4338ca", lineHeight: 1.5 }}><strong>Privacy Disclaimer:</strong> This view shows AI-generated risk signals only. No raw social media posts, messages, or personal content is stored or displayed. The AI processes anonymised patterns.</div>
                </div>

                {/* Youth Profile Card */}
                <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 18, marginBottom: 16 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>👤 Youth Profile</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
                    <div style={{ fontSize: 48, width: 64, height: 64, background: "linear-gradient(135deg, #ddd6fe, #e0e7ff)", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center" }}>{selectedCase.youth.avatar}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#1e293b", marginBottom: 2 }}>{selectedCase.youth.name}</div>
                      <div style={{ fontSize: 13, color: "#64748b", marginBottom: 4 }}>Age: {selectedCase.youth.age} · Instagram: {selectedCase.youth.handle}</div>
                      <button onClick={() => window.open(selectedCase.youth.instagramUrl, '_blank')} style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", border: "none", borderRadius: 8, padding: "6px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, marginTop: 6 }} onMouseEnter={e => e.currentTarget.style.opacity = "0.9"} onMouseLeave={e => e.currentTarget.style.opacity = "1"}>
                        📩 Reach Out via Instagram
                      </button>
                    </div>
                  </div>
                  <div style={{ background: "#fef3c7", border: "1px solid #fbbf24", borderRadius: 8, padding: "8px 12px", fontSize: 11, color: "#92400e", display: "flex", alignItems: "flex-start", gap: 8 }}>
                    <span>⚠️</span>
                    <div><strong>Important:</strong> Always use trauma-informed communication. Review SCS outreach protocols before initiating contact.</div>
                  </div>
                </div>

                {/* Risk meter */}
                <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 18, marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>Risk Score</span>
                    <span style={{ fontSize: 22, fontWeight: 800, color: RISK_COLORS[selectedCase.riskLevel].text }}>{selectedCase.riskLevel}<span style={{ fontSize: 14, fontWeight: 400, color: "#94a3b8" }}>/5</span></span>
                  </div>
                  <div style={{ display: "flex", gap: 4, height: 10, borderRadius: 5, overflow: "hidden" }}>
                    {[1,2,3,4,5].map(i => <div key={i} style={{ flex: 1, background: i <= selectedCase.riskLevel ? RISK_COLORS[selectedCase.riskLevel].text : "#e2e8f0", borderRadius: 5 }}></div>)}
                  </div>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 6 }}>{RISK_COLORS[selectedCase.riskLevel].label} risk · Category: {selectedCase.category}</div>
                </div>

                {/* AI Explanation Signals */}
                <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 18, marginBottom: 16 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>🤖 AI Explanation Signals <span style={{ fontSize: 10, color: "#94a3b8", fontWeight: 400 }}>(why this was flagged)</span></div>
                  {selectedCase.signals.map((s, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 0", borderBottom: i < selectedCase.signals.length - 1 ? "1px solid #f1f5f9" : "none" }}>
                      <span style={{ background: "#eef2ff", color: "#6366f1", borderRadius: 6, width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, flexShrink: 0, marginTop: 1 }}>{i + 1}</span>
                      <span style={{ fontSize: 13, color: "#475569", lineHeight: 1.5 }}>{s}</span>
                    </div>
                  ))}
                </div>

                {/* Summary */}
                <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e2e8f0", padding: 18 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>📝 Case Summary</div>
                  <p style={{ margin: 0, fontSize: 13, color: "#475569", lineHeight: 1.6 }}>{selectedCase.summary}</p>
                </div>
              </div>

              {/* Right col: Checklist */}
              <ChecklistPanel caseId={selectedCase.id} highlight={highlightTarget === "checklist-panel"} />
            </div>
          </div>
        )}

        {/* ── EMPTY STATE ── */}
        {!selectedCase && activeTab === "assigned" && (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>👆</div>
              <div style={{ fontSize: 15, fontWeight: 600, color: "#64748b" }}>Select a case to view details</div>
              <div style={{ fontSize: 13, marginTop: 4 }}>Click any card in your assigned list</div>
            </div>
          </div>
        )}
      </div>

      {/* ── CHATBOT TOGGLE ── */}
      <button onClick={() => setShowChatbot(s => !s)} style={{ position: "fixed", bottom: 24, right: 24, width: 56, height: 56, borderRadius: "50%", background: showChatbot ? "#dc2626" : "linear-gradient(135deg, #6366f1, #8b5cf6)", border: "none", color: "#fff", cursor: "pointer", fontSize: 24, boxShadow: "0 4px 18px rgba(99,102,241,0.45)", zIndex: 150, display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s" }} id="chatbot-area">
        {showChatbot ? "✕" : "💬"}
      </button>

      {/* ── CHATBOT PANEL ── */}
      {showChatbot && <ChatbotPanel assignedCases={myAssignedCases} highlight={highlightTarget === "chatbot-area"} />}
    </div>
  );
}

// ─── CHECKLIST PANEL ─────────────────────────────────────────────────
function ChecklistPanel({ caseId, highlight }) {
  const [items, setItems] = useState([
    { id: 1, label: "Outreach attempted", done: false, mandatory: true },
    { id: 2, label: "Response received", done: false, mandatory: true },
    { id: 3, label: "Follow-up scheduled", done: false, mandatory: true },
    { id: 4, label: "Escalation considered", done: false, mandatory: true },
    { id: 5, label: "Case closed", done: false, mandatory: true },
  ]);
  const [comments, setComments] = useState([]);
  const [newItem, setNewItem] = useState("");
  const [newComment, setNewComment] = useState("");
  const [addingItem, setAddingItem] = useState(false);

  const toggle = id => setItems(prev => prev.map(i => i.id === id ? { ...i, done: !i.done } : i));
  const addItem = () => { if (newItem.trim()) { setItems(prev => [...prev, { id: Date.now(), label: newItem.trim(), done: false, mandatory: false }]); setNewItem(""); setAddingItem(false); } };
  const addComment = () => { if (newComment.trim()) { setComments(prev => [...prev, { id: Date.now(), text: newComment.trim(), time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]); setNewComment(""); } };

  const mandatoryDone = items.filter(i => i.mandatory).every(i => i.done);
  const progress = Math.round((items.filter(i => i.done).length / items.length) * 100);

  return (
    <div id="checklist-panel" style={{ width: 320, background: "#fff", borderLeft: "1px solid #e2e8f0", display: "flex", flexDirection: "column", overflowY: "auto", flexShrink: 0, border: highlight ? "2px solid #6366f1" : undefined, boxShadow: highlight ? "0 0 0 3px rgba(99,102,241,0.2)" : undefined, transition: "all 0.3s" }}>
      {/* Header */}
      <div style={{ padding: "14px 18px", borderBottom: "1px solid #e2e8f0", background: "#fafafa" }}>
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>✅ Case Checklist</div>
        {/* Progress bar */}
        <div style={{ background: "#e2e8f0", borderRadius: 4, height: 6, overflow: "hidden" }}>
          <div style={{ width: `${progress}%`, height: "100%", background: mandatoryDone ? "#10b981" : "#6366f1", borderRadius: 4, transition: "width 0.4s" }}></div>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>{items.filter(i => i.done).length}/{items.length} complete {mandatoryDone && "· ✓ All mandatory items done"}</div>
      </div>

      {/* Mandatory items */}
      <div style={{ padding: "12px 18px 0" }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: "#dc2626", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 6 }}>🔹 Mandatory Steps</div>
        {items.filter(i => i.mandatory).map(item => (
          <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: "1px solid #f1f5f9" }}>
            <div onClick={() => toggle(item.id)} style={{ width: 20, height: 20, borderRadius: 5, border: item.done ? "none" : "2px solid #d1d5db", background: item.done ? "#6366f1" : "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.15s" }}>
              {item.done && <span style={{ color: "#fff", fontSize: 13 }}>✓</span>}
            </div>
            <span style={{ fontSize: 13, color: item.done ? "#94a3b8" : "#1e293b", textDecoration: item.done ? "line-through" : "none", flex: 1 }}>{item.label}</span>
          </div>
        ))}
      </div>

      {/* Custom items */}
      {items.filter(i => !i.mandatory).length > 0 && (
        <div style={{ padding: "12px 18px 0" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#6366f1", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 6 }}>📌 Custom Items</div>
          {items.filter(i => !i.mandatory).map(item => (
            <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 0" }}>
              <div onClick={() => toggle(item.id)} style={{ width: 20, height: 20, borderRadius: 5, border: item.done ? "none" : "2px solid #d1d5db", background: item.done ? "#8b5cf6" : "#fff", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                {item.done && <span style={{ color: "#fff", fontSize: 13 }}>✓</span>}
              </div>
              <span style={{ fontSize: 13, color: item.done ? "#94a3b8" : "#1e293b", textDecoration: item.done ? "line-through" : "none" }}>{item.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Add custom item */}
      <div style={{ padding: "10px 18px" }}>
        {addingItem ? (
          <div style={{ display: "flex", gap: 6 }}>
            <input autoFocus value={newItem} onChange={e => setNewItem(e.target.value)} onKeyDown={e => e.key === "Enter" && addItem()} placeholder="New checklist item..." style={{ flex: 1, padding: "6px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 13, outline: "none" }} />
            <button onClick={addItem} style={{ background: "#6366f1", color: "#fff", border: "none", borderRadius: 8, padding: "4px 12px", cursor: "pointer", fontSize: 13 }}>+</button>
            <button onClick={() => { setAddingItem(false); setNewItem(""); }} style={{ background: "#f1f5f9", border: "none", borderRadius: 8, padding: "4px 8px", cursor: "pointer", color: "#64748b" }}>✕</button>
          </div>
        ) : (
          <button onClick={() => setAddingItem(true)} style={{ width: "100%", background: "#f8fafc", border: "1px dashed #cbd5e1", borderRadius: 8, padding: "7px", cursor: "pointer", color: "#6366f1", fontSize: 13, fontWeight: 600 }}>+ Add custom item</button>
        )}
      </div>

      {/* Comments */}
      <div style={{ borderTop: "1px solid #e2e8f0", padding: "12px 18px", flex: 1 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 8 }}>💬 Comments</div>
        <div style={{ maxHeight: 120, overflowY: "auto", marginBottom: 8 }}>
          {comments.length === 0 && <div style={{ fontSize: 12, color: "#94a3b8", fontStyle: "italic" }}>No comments yet.</div>}
          {comments.map(c => (
            <div key={c.id} style={{ background: "#f8fafc", borderRadius: 8, padding: "8px 10px", marginBottom: 6, border: "1px solid #f1f5f9" }}>
              <div style={{ fontSize: 12, color: "#475569" }}>{c.text}</div>
              <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 3 }}>{c.time} · Sarah L.</div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <input value={newComment} onChange={e => setNewComment(e.target.value)} onKeyDown={e => e.key === "Enter" && addComment()} placeholder="Add a comment..." style={{ flex: 1, padding: "7px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 12, outline: "none" }} />
          <button onClick={addComment} style={{ background: "#6366f1", color: "#fff", border: "none", borderRadius: 8, padding: "4px 12px", cursor: "pointer", fontSize: 13 }}>→</button>
        </div>
      </div>
    </div>
  );
}

// ─── CHATBOT PANEL ───────────────────────────────────────────────────
function ChatbotPanel({ assignedCases, highlight }) {
  const [messages, setMessages] = useState([{ role: "bot", text: "👋 Hello! I'm the SCS Recommendation Assistant. I can help you with case guidance based on SCS protocols.\n\nUse the 📎 icon to attach one of your cases, or try a quick-action question below.\n\n⚠️ *I assist with guidance only. All outreach decisions are yours.*" }]);
  const [input, setInput] = useState("");
  const [attachedCase, setAttachedCase] = useState(null);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = (text) => {
    const t = text || input;
    if (!t.trim()) return;
    setMessages(prev => [...prev, { role: "user", text: t, attached: attachedCase }]);
    setInput("");
    setTimeout(() => {
      setMessages(prev => [...prev, { role: "bot", text: getChatbotResponse(t, attachedCase) }]);
    }, 600);
  };

  const renderText = (text) => {
    return text.split("\n").map((line, i) => {
      let rendered = line
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em style="color:#94a3b8">$1</em>');
      if (line.startsWith("| ")) {
        // Table row
        const cells = line.split("|").filter(c => c.trim());
        if (i > 0 && text.split("\n")[i - 1]?.startsWith("|---")) return null;
        if (line.includes("---")) return null;
        const isHeader = i === 0 || (text.split("\n").indexOf(line) === 0);
        return (
          <div key={i} style={{ display: "flex", borderBottom: "1px solid #e2e8f0", background: isHeader ? "#f1f5f9" : "transparent" }}>
            {cells.map((c, j) => <div key={j} style={{ flex: 1, padding: "4px 6px", fontSize: 11, fontWeight: isHeader ? 600 : 400, color: "#475569" }}>{c.trim()}</div>)}
          </div>
        );
      }
      return <div key={i} style={{ fontSize: 13, color: "#475569", lineHeight: 1.55, minHeight: line === "" ? 10 : "auto" }} dangerouslySetInnerHTML={{ __html: rendered }}></div>;
    });
  };

  return (
    <div id="chatbot-area" style={{ position: "fixed", bottom: 80, right: 24, width: 400, height: 520, background: "#fff", borderRadius: 18, boxShadow: "0 12px 48px rgba(0,0,0,0.2)", border: highlight ? "2px solid #6366f1" : "1px solid #e2e8f0", display: "flex", flexDirection: "column", overflow: "hidden", zIndex: 150, transition: "border 0.3s" }}>
      {/* Header */}
      <div style={{ background: "linear-gradient(135deg, #1e293b, #0f172a)", color: "#fff", padding: "12px 16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg, #6366f1, #8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>🤖</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>SCS Recommendation Assistant</div>
            <div style={{ fontSize: 10, color: "#94a3b8" }}>Guidance based on SCS Protocols</div>
          </div>
        </div>
      </div>

      {/* Attached case badge */}
      {attachedCase && (
        <div style={{ background: "#eef2ff", padding: "6px 14px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #c7d2fe" }}>
          <div style={{ fontSize: 12, color: "#4338ca" }}>📎 <strong>{attachedCase.code}</strong> — {attachedCase.category} (Risk {attachedCase.riskLevel})</div>
          <button onClick={() => setAttachedCase(null)} style={{ background: "none", border: "none", color: "#6366f1", cursor: "pointer", fontSize: 13 }}>✕</button>
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{ maxWidth: "85%", background: m.role === "user" ? "linear-gradient(135deg, #6366f1, #8b5cf6)" : "#f8fafc", color: m.role === "user" ? "#fff" : "#1e293b", borderRadius: m.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px", padding: "10px 14px", border: m.role === "bot" ? "1px solid #e2e8f0" : "none" }}>
              {m.attached && m.role === "user" && <div style={{ fontSize: 10, color: m.role === "user" ? "rgba(255,255,255,0.7)" : "#94a3b8", marginBottom: 3 }}>📎 {m.attached.code}</div>}
              {m.role === "user" ? <div style={{ fontSize: 13 }}>{m.text}</div> : <div>{renderText(m.text)}</div>}
            </div>
          </div>
        ))}
        <div ref={bottomRef}></div>
      </div>

      {/* Quick actions */}
      <div style={{ padding: "8px 12px 0", borderTop: "1px solid #f1f5f9", display: "flex", gap: 6, overflowX: "auto", paddingBottom: 4 }}>
        {PRESET_QUESTIONS.map((p, i) => (
          <button key={i} onClick={() => send(p.q)} style={{ whiteSpace: "nowrap", background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 20, padding: "5px 12px", fontSize: 11, cursor: "pointer", color: "#475569", display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }} onMouseEnter={e => e.currentTarget.style.background = "#e0e7ff"} onMouseLeave={e => e.currentTarget.style.background = "#f1f5f9"}>
            {p.icon} {p.label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div style={{ padding: "8px 12px 12px", display: "flex", gap: 8, alignItems: "center" }}>
        {/* Paperclip */}
        <div style={{ position: "relative" }}>
          <button onClick={() => setShowAttachMenu(!showAttachMenu)} style={{ background: "#f1f5f9", border: "1px solid #e2e8f0", borderRadius: 8, width: 36, height: 36, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, color: attachedCase ? "#6366f1" : "#94a3b8" }} title="Attach a case">📎</button>
          {showAttachMenu && (
            <div style={{ position: "absolute", bottom: "calc(100% + 6px)", left: 0, background: "#fff", borderRadius: 12, boxShadow: "0 8px 30px rgba(0,0,0,0.18)", width: 240, zIndex: 10, overflow: "hidden" }}>
              <div style={{ padding: "8px 12px 4px", fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.8px" }}>Attach a case</div>
              {assignedCases.map(c => (
                <button key={c.id} onClick={() => { setAttachedCase(c); setShowAttachMenu(false); }} style={{ width: "100%", textAlign: "left", background: attachedCase?.id === c.id ? "#eef2ff" : "none", border: "none", padding: "8px 12px", cursor: "pointer", fontSize: 12, color: "#1e293b", display: "flex", alignItems: "center", gap: 8 }} onMouseEnter={e => e.currentTarget.style.background = "#f8fafc"} onMouseLeave={e => e.currentTarget.style.background = attachedCase?.id === c.id ? "#eef2ff" : "none"}>
                  <RiskBadge level={c.riskLevel} />
                  <span style={{ fontWeight: 600 }}>{c.code}</span>
                  <span style={{ color: "#94a3b8" }}>{c.category}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder="Ask for guidance..." style={{ flex: 1, padding: "8px 12px", borderRadius: 10, border: "1px solid #d1d5db", fontSize: 13, outline: "none" }} />
        <button onClick={() => send()} style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff", border: "none", borderRadius: 10, width: 36, height: 36, cursor: "pointer", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center" }}>→</button>
      </div>
    </div>
  );
}
