import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import { Icon } from "../components/Icons.jsx";
import { caseAPI, userAPI, historyAPI, transformCase } from "../services/api.js";

// ─── Service URLs ──────────────────────────────────────────────────────────────
const CASE_SERVICE_URL = "http://localhost:8001";

// ─── Design tokens ─────────────────────────────────────────────────────────────
const T = {
  navy:    "#0f172a",
  navyMid: "#1e293b",
  slate:   "#475569",
  muted:   "#94a3b8",
  border:  "#e2e8f0",
  bg:      "#f0f4f8",
  white:   "#ffffff",
  indigo:  "#6366f1",
  violet:  "#8b5cf6",
  success: "#10b981",
  danger:  "#dc2626",
  warn:    "#f59e0b",
};

// ─── Status config ──────────────────────────────────────────────────────────────
const STATUS_CFG = {
  new:         { label: "New",         dot: "#6366f1", bg: "#eef2ff", text: "#3730a3" },
  in_progress: { label: "In Progress", dot: "#f59e0b", bg: "#fffbeb", text: "#92400e" },
  in_review:   { label: "In Review",   dot: "#dc2626", bg: "#fef2f2", text: "#991b1b" },
  outreach:    { label: "Outreach",    dot: "#8b5cf6", bg: "#f5f3ff", text: "#5b21b6" },
  followup:    { label: "Follow-up",   dot: "#0ea5e9", bg: "#f0f9ff", text: "#0369a1" },
  completed:   { label: "Completed",   dot: "#10b981", bg: "#ecfdf5", text: "#065f46" },
  closed:      { label: "Closed",      dot: "#94a3b8", bg: "#f8fafc", text: "#475569" },
  // Frontend-generated
  Active:      { label: "Active",      dot: "#6366f1", bg: "#eef2ff", text: "#3730a3" },
  Escalated:   { label: "Escalated",   dot: "#dc2626", bg: "#fef2f2", text: "#991b1b" },
  Monitoring:  { label: "Monitoring",  dot: "#94a3b8", bg: "#f8fafc", text: "#475569" },
  Pending:     { label: "Pending",     dot: "#f59e0b", bg: "#fffbeb", text: "#92400e" },
};

const CASE_STATUS_CFG = {
  new:        { label: "New",                   dot: "#6366f1", bg: "#eef2ff", text: "#3730a3" },
  unassigned: { label: "Unassigned",            dot: "#94a3b8", bg: "#f8fafc", text: "#475569" },
  assigned:   { label: "Assigned",              dot: "#10b981", bg: "#ecfdf5", text: "#065f46" },
  reassigned: { label: "Pending Reassignment",  dot: "#f59e0b", bg: "#fffbeb", text: "#92400e" },
};

const WORK_STATUS_CFG = {
  not_started:  { label: "Not Started", dot: "#94a3b8", bg: "#f8fafc", text: "#475569" },
  in_progress:  { label: "In Progress", dot: "#3b82f6", bg: "#dbeafe", text: "#1e40af" },
  to_review:    { label: "To Review",   dot: "#dc2626", bg: "#fee2e2", text: "#991b1b" },
  completed:    { label: "Completed",   dot: "#10b981", bg: "#ecfdf5", text: "#065f46" },
};

const RISK_CFG = {
  1: { label: "Low",      bg: "#d1fae5", text: "#065f46" },
  2: { label: "Low-Med",  bg: "#dbeafe", text: "#1e40af" },
  3: { label: "Medium",   bg: "#fef3c7", text: "#92400e" },
  4: { label: "High",     bg: "#ffedd5", text: "#c2410c" },
  5: { label: "Critical", bg: "#fee2e2", text: "#991b1b" },
};

// ─── Small shared sub-components ───────────────────────────────────────────────
function StatusBadge({ status }) {
  const raw = (status || "").toLowerCase().replace(" ", "_");
  const cfg = STATUS_CFG[raw] || STATUS_CFG[status] || { label: status, dot: "#94a3b8", bg: "#f8fafc", text: "#475569" };
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:5, background:cfg.bg, color:cfg.text, padding:"3px 9px", borderRadius:20, fontSize:11, fontWeight:600, whiteSpace:"nowrap" }}>
      <span style={{ width:5, height:5, borderRadius:"50%", background:cfg.dot, flexShrink:0 }}/>
      {cfg.label || status}
    </span>
  );
}

function RiskBadge({ level, score }) {
  const c = RISK_CFG[level] || RISK_CFG[3];
  const displayScore = score ? `${score.toFixed(1)}%` : `${c.label} ${level}/5`;
  return (
    <span style={{ background:c.bg, color:c.text, padding:"2px 9px", borderRadius:20, fontSize:11, fontWeight:700, whiteSpace:"nowrap" }}>
      {displayScore}
    </span>
  );
}

function CaseStatusBadge({ caseStatus }) {
  const cfg = CASE_STATUS_CFG[(caseStatus||"").toLowerCase()] || { label: caseStatus || "—", dot: "#94a3b8", bg: "#f8fafc", text: "#475569" };
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:5, background:cfg.bg, color:cfg.text, padding:"2px 9px", borderRadius:20, fontSize:11, fontWeight:600, whiteSpace:"nowrap" }}>
      <span style={{ width:5, height:5, borderRadius:"50%", background:cfg.dot, flexShrink:0 }}/>
      {cfg.label}
    </span>
  );
}

function WorkStatusBadge({ workStatus }) {
  const cfg = WORK_STATUS_CFG[(workStatus||"").toLowerCase()] || { label: workStatus || "—", dot: "#94a3b8", bg: "#f8fafc", text: "#475569" };
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:5, background:cfg.bg, color:cfg.text, padding:"2px 9px", borderRadius:20, fontSize:11, fontWeight:600, whiteSpace:"nowrap" }}>
      <span style={{ width:5, height:5, borderRadius:"50%", background:cfg.dot, flexShrink:0 }}/>
      {cfg.label}
    </span>
  );
}

function PriorityDot({ priority }) {
  const map = { critical:"#dc2626", high:"#f97316", medium:"#f59e0b", low:"#10b981" };
  return <span style={{ display:"inline-block", width:8, height:8, borderRadius:"50%", background:map[priority]||"#94a3b8", marginRight:5 }} title={priority}/>;
}

function Avatar({ initials, size=28 }) {
  return (
    <div style={{ width:size, height:size, borderRadius:"50%", background:"linear-gradient(135deg,#6366f1,#8b5cf6)", color:"#fff", fontSize:size*0.38, fontWeight:700, display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0 }}>
      {initials}
    </div>
  );
}

// ─── Case Detail Panel (admin read/action view) ────────────────────────────────
function AdminCaseDetail({ c, helpers, onClose, onAssign, currentUser }) {
  const [history, setHistory]  = useState([]);
  const [assigning, setAssigning] = useState(false);
  const [selectedHelper, setSelectedHelper] = useState(c.assigned_to || "");
  const [assignMsg, setAssignMsg] = useState("");

  useEffect(() => {
    historyAPI.getCaseHistory(c.case_id)
      .then(data => setHistory(data || []))
      .catch(() => setHistory([]));
  }, [c.case_id]);

  const handleAssign = async () => {
    try {
      const res = await fetch(`${CASE_SERVICE_URL}/cases/${c.case_id}/assign`, {
        method:"PATCH",
        headers:{ "Content-Type":"application/json", "X-User-Id":currentUser.user_id, "X-User-Role":"Admin" },
        body: JSON.stringify({ assigned_to: selectedHelper || null }),
      });
      if (res.ok) {
        setAssignMsg("Assigned successfully.");
        onAssign(c.case_id, selectedHelper);
        setAssigning(false);
      } else {
        setAssignMsg("API unavailable — assignment saved locally.");
        onAssign(c.case_id, selectedHelper);
        setAssigning(false);
      }
    } catch {
      setAssignMsg("API unavailable — reflected in table.");
      onAssign(c.case_id, selectedHelper);
      setAssigning(false);
    }
  };

  const riskLevel = c.riskLevel || c.risk_score || 3;
  const signals = c.explanation_signals?.risk_indicators || c.signals || ["No signal data available."];

  return (
    <div style={{ position:"fixed", inset:0, zIndex:9999, background:"rgba(0,0,0,0.5)", display:"flex", alignItems:"center", justifyContent:"center", padding:20 }}>
      <div style={{ width:"90%", maxWidth:1200, height:"90vh", background:"#fff", borderRadius:16, boxShadow:"0 20px 60px rgba(0,0,0,0.3)", display:"flex", flexDirection:"column", overflow:"hidden" }}>
      {/* Header */}
      <div style={{ padding:"16px 20px", borderBottom:`1px solid ${T.border}`, background:"#fafafa", display:"flex", alignItems:"center", gap:12 }}>
        <button onClick={onClose} style={{ background:T.bg, border:"none", borderRadius:8, width:32, height:32, cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", color:T.slate }}>
          <Icon.X size={16} />
        </button>
        <div style={{ flex:1 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ fontWeight:700, fontSize:15, color:T.navyMid }}>{c.case_id || c.code}</span>
            <RiskBadge level={riskLevel} score={c.current_risk_score || c.risk_score} />
          </div>
          <div style={{ fontSize:12, color:T.muted, marginTop:2 }}>{c.platform} · {c.category}</div>
        </div>
        <StatusBadge status={c.status} />
      </div>

      <div style={{ flex:1, overflowY:"auto", padding:20, display:"flex", flexDirection:"column", gap:16 }}>
        {/* Admin actions */}
        <div style={{ background:"#f8fafc", border:`1px solid ${T.border}`, borderRadius:10, padding:14 }}>
          <div style={{ fontSize:11, fontWeight:700, color:T.muted, textTransform:"uppercase", letterSpacing:"0.8px", marginBottom:10 }}>Admin Actions</div>

          {assignMsg && (
            <div style={{ background:"#ecfdf5", border:"1px solid #6ee7b7", borderRadius:7, padding:"6px 10px", fontSize:12, color:"#065f46", marginBottom:10, display:"flex", alignItems:"center", gap:6 }}>
              <Icon.CheckCircle size={13} color="#10b981"/>{assignMsg}
            </div>
          )}

          {assigning ? (
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              <select
                value={selectedHelper}
                onChange={e => setSelectedHelper(e.target.value)}
                style={{ padding:"8px 10px", fontSize:13, borderRadius:8, border:`1px solid ${T.border}`, outline:"none", background:"#fff" }}
              >
                <option value="">— Unassigned —</option>
                {helpers.map(h => (
                  <option key={h.user_id} value={h.user_id}>
                    {h.name} ({h.employee_id}) · {h.department}
                  </option>
                ))}
              </select>
              <div style={{ display:"flex", gap:8 }}>
                <button onClick={handleAssign} style={{ flex:1, background:T.indigo, color:"#fff", border:"none", borderRadius:8, padding:"8px", fontSize:13, fontWeight:600, cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", gap:6 }}>
                  <Icon.UserCheck size={14} color="#fff" /> Confirm Assignment
                </button>
                <button onClick={()=>setAssigning(false)} style={{ background:T.bg, color:T.slate, border:`1px solid ${T.border}`, borderRadius:8, padding:"8px 14px", fontSize:13, cursor:"pointer" }}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
              <button onClick={()=>setAssigning(true)} style={{ display:"flex", alignItems:"center", gap:6, background:T.indigo, color:"#fff", border:"none", borderRadius:8, padding:"7px 14px", fontSize:12, fontWeight:600, cursor:"pointer" }}>
                <Icon.UserCheck size={13} color="#fff" />{c.assigned_to && c.assigned_to !== "—" ? "Reassign" : "Assign to Helper"}
              </button>
              <button style={{ display:"flex", alignItems:"center", gap:6, background:"#f8fafc", color:T.slate, border:`1px solid ${T.border}`, borderRadius:8, padding:"7px 14px", fontSize:12, fontWeight:600, cursor:"pointer" }}>
                <Icon.CheckCircle size={13} color="#10b981"/>Mark Resolved
              </button>
            </div>
          )}

          {/* Current assignment */}
          <div style={{ marginTop:12, fontSize:12, color:T.slate, display:"flex", alignItems:"center", gap:6 }}>
            <Icon.User size={12} color={T.muted}/>
            <span>Assigned to: <strong>{c.assigned_to ? helpers.find(h=>h.user_id===c.assigned_to)?.name || c.assigned_to : "Unassigned"}</strong></span>
          </div>
        </div>

        {/* AI Signals */}
        <div style={{ background:"#fff", border:`1px solid ${T.border}`, borderRadius:10, padding:14 }}>
          <div style={{ fontSize:11, fontWeight:700, color:T.muted, textTransform:"uppercase", letterSpacing:"0.8px", marginBottom:10, display:"flex", alignItems:"center", gap:6 }}>
            <Icon.Activity size={12} color={T.indigo}/> AI Explanation Signals
          </div>
          {signals.map((s, i) => (
            <div key={i} style={{ display:"flex", gap:8, padding:"7px 0", borderBottom:i<signals.length-1?`1px solid #f1f5f9`:"none" }}>
              <span style={{ background:"#eef2ff", color:T.indigo, borderRadius:5, width:20, height:20, display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, fontWeight:700, flexShrink:0 }}>{i+1}</span>
              <span style={{ fontSize:12, color:T.slate, lineHeight:1.5 }}>{s}</span>
            </div>
          ))}
        </div>

        {/* Ingestion History */}
        {history.length > 0 && (
          <div style={{ background:"#fff", border:`1px solid ${T.border}`, borderRadius:10, padding:14 }}>
            <div style={{ fontSize:11, fontWeight:700, color:T.muted, textTransform:"uppercase", letterSpacing:"0.8px", marginBottom:10, display:"flex", alignItems:"center", gap:6 }}>
              <Icon.Clock size={12} color={T.indigo}/> Case History Timeline
            </div>
            <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
              {history.slice().reverse().slice(0,5).map((entry, i) => {
                const isLatest = i === 0;
                const date = new Date(entry.ingestion_date);
                const formattedDate = date.toLocaleDateString('en-US', {
                  year: 'numeric', month: 'short', day: 'numeric',
                  hour: '2-digit', minute: '2-digit'
                });
                
                // Extract signals from AI explanation
                const signals = (entry.ai_explanation || "")
                  .split('\n')
                  .filter(line => line.trim().startsWith('•') || line.trim().startsWith('-'))
                  .map(line => line.replace(/^[•\-]\s*/, '').trim())
                  .filter(Boolean);
                
                // Risk level coloring
                const getRiskColor = (score) => {
                  if (score >= 90) return { bg: '#fef2f2', text: '#dc2626', label: 'Critical' };
                  if (score >= 75) return { bg: '#fff3e0', text: '#f59e0b', label: 'High' };
                  if (score >= 50) return { bg: '#fefce8', text: '#eab308', label: 'Medium' };
                  if (score >= 25) return { bg: '#eff6ff', text: '#3b82f6', label: 'Low-Medium' };
                  return { bg: '#f0fdf4', text: '#10b981', label: 'Low' };
                };
                
                const riskColor = getRiskColor(entry.risk_score);
                
                return (
                  <div key={entry.history_id || i} style={{
                    background: isLatest ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)' : '#ffffff',
                    border: isLatest ? 'none' : `1px solid ${T.border}`,
                    borderRadius: 8,
                    padding: isLatest ? 12 : 10,
                    boxShadow: isLatest ? '0 4px 6px -1px rgba(99, 102, 241, 0.2)' : '0 1px 2px rgba(0,0,0,0.05)',
                  }}>
                    {/* Date Header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Icon.Calendar size={13} color={isLatest ? '#ffffff' : T.indigo} />
                        <span style={{
                          fontSize: 11.5,
                          fontWeight: 600,
                          color: isLatest ? '#ffffff' : T.navyMid
                        }}>
                          {formattedDate}
                        </span>
                      </div>
                      {isLatest && (
                        <span style={{
                          fontSize: 9,
                          fontWeight: 700,
                          color: '#ffffff',
                          background: 'rgba(255,255,255,0.25)',
                          padding: '2px 6px',
                          borderRadius: 4,
                          letterSpacing: '0.5px'
                        }}>LATEST</span>
                      )}
                    </div>
                    
                    {/* Risk Score Badge */}
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      background: isLatest ? 'rgba(255,255,255,0.95)' : riskColor.bg,
                      padding: '6px 10px',
                      borderRadius: 6,
                      marginBottom: signals.length > 0 ? 10 : 0
                    }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: riskColor.text }}>
                        {entry.risk_score}%
                      </span>
                      <span style={{ fontSize: 10, fontWeight: 600, color: riskColor.text, opacity: 0.8 }}>
                        {riskColor.label} Risk
                      </span>
                    </div>
                    
                    {/* AI Signals */}
                    {signals.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <div style={{
                          fontSize: 10,
                          fontWeight: 600,
                          color: isLatest ? 'rgba(255,255,255,0.85)' : T.muted,
                          marginBottom: 6,
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px'
                        }}>AI Signals Detected:</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          {signals.map((signal, idx) => (
                            <div key={idx} style={{
                              background: isLatest ? 'rgba(255,255,255,0.15)' : '#f8fafc',
                              padding: '6px 8px',
                              borderRadius: 5,
                              borderLeft: `3px solid ${isLatest ? '#ffffff' : '#6366f1'}`,
                              display: 'flex',
                              gap: 8,
                              alignItems: 'flex-start'
                            }}>
                              <span style={{
                                fontSize: 10,
                                fontWeight: 700,
                                color: isLatest ? '#ffffff' : T.indigo,
                                flexShrink: 0,
                                width: 16,
                                height: 16,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: isLatest ? 'rgba(255,255,255,0.25)' : '#eef2ff',
                                borderRadius: 3
                              }}>{idx + 1}</span>
                              <span style={{
                                fontSize: 11,
                                color: isLatest ? 'rgba(255,255,255,0.95)' : T.slate,
                                lineHeight: 1.5
                              }}>{signal}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {/* Metadata Footer */}
                    <div style={{
                      display: 'flex',
                      gap: 10,
                      marginTop: 8,
                      fontSize: 10,
                      color: isLatest ? 'rgba(255,255,255,0.75)' : T.muted
                    }}>
                      <span>📂 {entry.category}</span>
                      <span>🤖 {entry.model_version}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Case metadata */}
        <div style={{ background:"#f8fafc", border:`1px solid ${T.border}`, borderRadius:10, padding:12 }}>
          <div style={{ fontSize:11, fontWeight:700, color:T.muted, textTransform:"uppercase", letterSpacing:"0.8px", marginBottom:8 }}>Case Metadata</div>
          {[
            ["Case ID",    c.case_id||c.code],
            ["Youth Handle", c.user_id || c.youth?.handle || "—"],
            ["Category",   c.category],
            ["Platform",   c.platform||"Instagram"],
            ["Priority",   c.priority||"—"],
            ["Last Signal",c.lastSignal||c.last_signal_at||"—"],
          ].map(([k,v]) => (
            <div key={k} style={{ display:"flex", justifyContent:"space-between", padding:"4px 0", borderBottom:"1px solid #f1f5f9", fontSize:12 }}>
              <span style={{ color:T.muted }}>{k}</span>
              <span style={{ color:T.navyMid, fontWeight:500, textAlign:"right", maxWidth:200, overflow:"hidden", textOverflow:"ellipsis" }}>{v}</span>
            </div>
          ))}
        </div>
      </div>      </div>    </div>
  );
}

// ─── Assignment Modal ─────────────────────────────────────────────────────────
function AssignModal({ caseRow, helpers, currentUser, onConfirm, onClose }) {
  const [selectedHelper, setSelectedHelper] = useState("");
  const [busy, setBusy] = useState(false);

  const handleConfirm = async () => {
    if (!selectedHelper) return;
    setBusy(true);
    try {
      await fetch(`${CASE_SERVICE_URL}/cases/${caseRow.case_id}/assign`, {
        method: "PATCH",
        headers: { "Content-Type":"application/json","X-User-Id":currentUser.user_id,"X-User-Role":"Admin" },
        body: JSON.stringify({ assigned_to: selectedHelper }),
      }).catch(() => {});
    } finally {
      onConfirm(caseRow.case_id, selectedHelper);
      setBusy(false);
    }
  };

  const helper = helpers.find(h => h.user_id === selectedHelper);

  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(15,23,42,0.55)", zIndex:400, display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{ background:"#fff", borderRadius:16, width:440, padding:28, boxShadow:"0 24px 60px rgba(0,0,0,0.35)" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:16 }}>
          <div style={{ fontWeight:700, fontSize:16, color:T.navyMid }}>Assign Case</div>
          <button onClick={onClose} style={{ background:T.bg, border:"none", borderRadius:8, width:30, height:30, cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center" }}>
            <Icon.X size={15} color={T.slate}/>
          </button>
        </div>

        <div style={{ background:"#f8fafc", border:`1px solid ${T.border}`, borderRadius:9, padding:"10px 14px", marginBottom:18 }}>
          <div style={{ fontSize:12, color:T.muted, marginBottom:4 }}>Case to assign</div>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ fontWeight:700, fontSize:14, color:T.navyMid }}>{caseRow.case_id}</span>
            <RiskBadge level={caseRow.riskLevel||caseRow.risk_score||3} score={caseRow.current_risk_score || caseRow.risk_score}/>
            <StatusBadge status={caseRow.status}/>
          </div>
          <div style={{ fontSize:12, color:T.slate, marginTop:3 }}>{caseRow.category} · {caseRow.platform||"Instagram"}</div>
        </div>

        <div style={{ marginBottom:16 }}>
          <label style={{ fontSize:12, fontWeight:600, color:T.navyMid, display:"block", marginBottom:6 }}>Select Youth Helper</label>
          <select
            value={selectedHelper}
            onChange={e => setSelectedHelper(e.target.value)}
            style={{ width:"100%", padding:"9px 10px", fontSize:13, borderRadius:9, border:`1.5px solid ${T.border}`, outline:"none", background:"#fafafa" }}
          >
            <option value="">— Select a helper —</option>
            {helpers.map(h => (
              <option key={h.user_id} value={h.user_id}>
                {h.employee_id} · {h.name} — {h.department}
              </option>
            ))}
          </select>
        </div>

        {helper && (
          <div style={{ background:"#eef2ff", border:"1px solid #c7d2fe", borderRadius:9, padding:"10px 14px", marginBottom:16, display:"flex", alignItems:"center", gap:10 }}>
            <Avatar initials={helper.avatar_initials} size={32}/>
            <div>
              <div style={{ fontWeight:600, fontSize:13, color:T.navyMid }}>{helper.name}</div>
              <div style={{ fontSize:11, color:T.muted }}>{helper.employee_id} · {helper.department}</div>
            </div>
          </div>
        )}

        <div style={{ display:"flex", gap:10 }}>
          <button
            onClick={handleConfirm}
            disabled={!selectedHelper || busy}
            style={{ flex:1, background:selectedHelper?"linear-gradient(135deg,#6366f1,#8b5cf6)":"#e2e8f0", color:selectedHelper?"#fff":"#94a3b8", border:"none", borderRadius:9, padding:"10px", fontWeight:700, fontSize:13, cursor:selectedHelper?"pointer":"default", transition:"all 0.2s", display:"flex", alignItems:"center", justifyContent:"center", gap:6 }}
          >
            <Icon.UserCheck size={14} color={selectedHelper?"#fff":"#94a3b8"}/>
            {busy?"Assigning…":"Confirm Assignment"}
          </button>
          <button onClick={onClose} style={{ background:T.bg, border:`1px solid ${T.border}`, borderRadius:9, padding:"10px 18px", fontSize:13, cursor:"pointer", color:T.slate }}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Full Admin Dashboard ─────────────────────────────────────────────────────
export default function AdminDashboard({ currentUser: propUser }) {
  const { user: authUser, logout } = useAuth();
  const currentUser = propUser || authUser;
  
  const [activeTab, setActiveTab]     = useState("all");
  const [cases, setCases]             = useState([]);
  const [reassignments, setReassignments] = useState([]);
  const [helpers, setHelpers]         = useState([]); // Fetch from MongoDB API
  const [selectedCase, setSelectedCase] = useState(null);
  const [assignModal, setAssignModal]   = useState(null); // caseRow | null
  const [search, setSearch]           = useState("");
  const [sortCol, setSortCol]         = useState("risk_score");
  const [sortDir, setSortDir]         = useState("desc");
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(null);

  // Fetch cases and users from MongoDB API
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch all cases from MongoDB
        const casesData = await caseAPI.getAllCases();
        const transformedCases = casesData.map(c => transformCase(c));
        setCases(transformedCases);

        // Fetch youth helpers from MongoDB
        try {
          const helpersData = await userAPI.getYouthHelpers();
          if (helpersData && helpersData.length > 0) {
            setHelpers(helpersData.map(h => ({
              user_id: h.user_id,
              name: h.username,
              employee_id: h.user_id,
              department: h.role,
              avatar_initials: h.username?.split(' ').map(n => n[0]).join('') || h.user_id?.substring(0, 2).toUpperCase()
            })));
          }
        } catch (err) {
          console.warn("Could not fetch helpers from API:", err);
        }

        setLoading(false);
      } catch (err) {
        console.error("Failed to load cases:", err);
        setError(err.message || "Failed to load data from database");
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // ── Tab filtering ──────────────────────────────────────────────────────────
  const allCases         = cases;
  const unassignedCases  = cases.filter(c => !c.assigned_to || c.assigned_to === "—");
  const needsReviewCases = cases.filter(c => c.needs_review || c.work_status === "to_review" || c.status === "in_review" || c.status === "Escalated");
  const pendingRequests  = reassignments.filter(r => r.status === "pending");

  const tabCounts = {
    all:          allCases.length,
    unassigned:   unassignedCases.length,
    review:       needsReviewCases.length,
    reassignment: pendingRequests.length,
  };

  // ── Sorting ────────────────────────────────────────────────────────────────
  const handleSort = (col) => {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("desc"); }
  };

  const sortedFn = (arr) => [...arr].sort((a, b) => {
    let va = a[sortCol], vb = b[sortCol];
    if (sortCol === "riskLevel") { va = a.riskLevel||a.risk_score||0; vb = b.riskLevel||b.risk_score||0; }
    if (typeof va === "number" && typeof vb === "number") return sortDir==="asc" ? va-vb : vb-va;
    va = String(va||""); vb = String(vb||"");
    return sortDir==="asc" ? va.localeCompare(vb) : vb.localeCompare(va);
  });

  const filterSearch = (arr) => {
    if (!search.trim()) return arr;
    const q = search.toLowerCase();
    return arr.filter(c =>
      (c.case_id||c.code||"").toLowerCase().includes(q) ||
      (c.category||"").toLowerCase().includes(q) ||
      (c.user_id||"").toLowerCase().includes(q) ||
      (c.assigned_to||"").toLowerCase().includes(q) ||
      (c.status||"").toLowerCase().includes(q)
    );
  };

  const activeCases = () => {
    const base = { all: allCases, unassigned: unassignedCases, review: needsReviewCases }[activeTab] || allCases;
    return sortedFn(filterSearch(base));
  };

  // ── Assignment handlers ────────────────────────────────────────────────────
  const handleAssignment = async (caseId, helperId) => {
    try {
      // Call API to assign case
      await caseAPI.assignCase(caseId, helperId);
      
      // Update local state
      setCases(prev => prev.map(c =>
        (c.case_id||c.code) === caseId
          ? {  ...c, assigned_to: helperId, status: c.status === "new" ? "in_progress" : c.status, case_status: helperId ? "assigned" : "unassigned", work_status: "not_started" }
          : c
      ));
      setAssignModal(null);
      if (selectedCase && (selectedCase.case_id||selectedCase.code) === caseId) {
        setSelectedCase(prev => ({ ...prev, assigned_to: helperId, case_status: helperId ? "assigned" : "unassigned", work_status: "not_started" }));
      }
    } catch (err) {
      console.error("Failed to assign case:", err);
      alert(`Failed to assign case: ${err.message}`);
    }
  };

  // ── Reassignment actions ───────────────────────────────────────────────────
  const handleReassignAction = async (id, action, targetHelper = null) => {
    try {
      await fetch(`${CASE_SERVICE_URL}/cases/reassignment-requests/${id}/${action}`, {
        method:"PATCH",
        headers:{ "Content-Type":"application/json","X-User-Id":currentUser.user_id,"X-User-Role":"Admin" },
        body: JSON.stringify({ reviewed_by: currentUser.user_id, ...(targetHelper ? { assigned_to: targetHelper } : {}) }),
      }).catch(() => {});
    } finally {
      setReassignments(prev => prev.map(r => r.id === id ? { ...r, status: action } : r));
      if (action === "approved") {
        // Update the case: clear reassigned flag, reset work status
        setReassignments(prev => {
          const req = prev.find(r => r.id === id);
          if (req) {
            setCases(cs => cs.map(c =>
              (c.case_id||c.code) === req.case_id
                ? { ...c, case_status: "assigned", work_status: "not_started", assigned_to: targetHelper || req.requested_to || c.assigned_to }
                : c
            ));
          }
          return prev;
        });
      }
    }
  };

  // ── Column header helper ───────────────────────────────────────────────────
  const ColHeader = ({ col, label, style }) => (
    <th
      onClick={() => handleSort(col)}
      style={{ padding:"9px 12px", textAlign:"left", fontSize:11, fontWeight:700, color:T.muted, textTransform:"uppercase", letterSpacing:"0.6px", cursor:"pointer", whiteSpace:"nowrap", userSelect:"none", background:"#f8fafc", borderBottom:`1px solid ${T.border}`, ...style }}
    >
      {label}
      {sortCol === col && <span style={{ marginLeft:4, fontSize:9 }}>{sortDir==="asc"?"▲":"▼"}</span>}
    </th>
  );

  // ── Case row ───────────────────────────────────────────────────────────────
  const CaseRow = ({ c, showAssignBtn = false }) => {
    const isSelected = selectedCase && (selectedCase.case_id||selectedCase.code) === (c.case_id||c.code);
    const helperObj  = helpers.find(h => h.user_id === c.assigned_to);
    const riskLevel  = c.riskLevel || c.risk_score || 3;
    return (
      <tr
        onClick={() => setSelectedCase(isSelected ? null : c)}
        style={{ borderBottom:`1px solid ${T.border}`, cursor:"pointer", background:isSelected?"#eef2ff":"#fff", transition:"background 0.15s" }}
        onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background="#f8fafc"; }}
        onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background="#fff"; }}
      >
        <td style={{ padding:"10px 12px", whiteSpace:"nowrap" }}>
          <PriorityDot priority={c.priority}/>
          <span style={{ fontWeight:700, fontSize:12, color:T.navyMid, fontFamily:"monospace" }}>{c.case_id||c.code}</span>
        </td>
        <td style={{ padding:"10px 12px", fontSize:12, color:T.slate, maxWidth:120, overflow:"hidden", textOverflow:"ellipsis" }}>
          {c.user_id || c.youth?.handle || "—"}
        </td>
        <td style={{ padding:"10px 12px" }}><RiskBadge level={riskLevel} score={c.current_risk_score || c.risk_score}/></td>
        <td style={{ padding:"10px 12px", fontSize:12, color:T.slate, whiteSpace:"nowrap" }}>{c.category}</td>
        <td style={{ padding:"10px 12px" }}>
          <CaseStatusBadge caseStatus={c.case_status} />
        </td>
        <td style={{ padding:"10px 12px" }}>
          <WorkStatusBadge workStatus={c.work_status} />
        </td>
        <td style={{ padding:"10px 12px" }}>
          {helperObj ? (
            <div style={{ display:"flex", alignItems:"center", gap:6 }}>
              <Avatar initials={helperObj.avatar_initials} size={22}/>
              <div>
                <div style={{ fontSize:12, fontWeight:600, color:T.navyMid }}>{helperObj.name}</div>
                <div style={{ fontSize:10, color:T.muted }}>{helperObj.employee_id}</div>
              </div>
            </div>
          ) : (
            <span style={{ fontSize:12, color:T.muted, fontStyle:"italic" }}>Unassigned</span>
          )}
        </td>
        <td style={{ padding:"10px 12px", fontSize:11, color:T.muted, whiteSpace:"nowrap" }}>
          <Icon.Clock size={11} color={T.muted} style={{ display:"inline", marginRight:4, verticalAlign:"middle" }}/>
          {(c.lastSignal||c.last_signal_at||"—").slice(0,16).replace("T"," ")}
        </td>
        <td style={{ padding:"10px 12px" }} onClick={e => e.stopPropagation()}>
          <div style={{ display:"flex", gap:6 }}>
            <button
              onClick={e => { e.stopPropagation(); setAssignModal(c); }}
              style={{ display:"flex", alignItems:"center", gap:4, background:T.indigo, color:"#fff", border:"none", borderRadius:7, padding:"4px 10px", fontSize:11, fontWeight:600, cursor:"pointer", whiteSpace:"nowrap" }}
            >
              <Icon.UserCheck size={11} color="#fff"/> {c.assigned_to && c.assigned_to !== "—" ? "Reassign" : "Assign"}
            </button>
            <button
              onClick={e => { e.stopPropagation(); setSelectedCase(isSelected ? null : c); }}
              style={{ display:"flex", alignItems:"center", gap:4, background:T.bg, color:T.slate, border:`1px solid ${T.border}`, borderRadius:7, padding:"4px 10px", fontSize:11, cursor:"pointer" }}
            >
              <Icon.Eye size={11}/> View
            </button>
          </div>
        </td>
      </tr>
    );
  };

  // ── Tabs config ────────────────────────────────────────────────────────────
  const TABS = [
    { id:"all",          icon:<Icon.List size={14}/>,          label:"All Cases",             count:tabCounts.all          },
    { id:"unassigned",   icon:<Icon.UserX size={14}/>,         label:"Unassigned",            count:tabCounts.unassigned   },
    { id:"review",       icon:<Icon.AlertTriangle size={14}/>, label:"Needs Review",          count:tabCounts.review       },
    { id:"reassignment", icon:<Icon.RefreshCw size={14}/>,     label:"Reassignment Requests", count:pendingRequests.length },
  ];

  // Loading state
  if (loading) {
    return (
      <div style={{ fontFamily:"'Segoe UI', system-ui, sans-serif", background:T.bg, minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center", flexDirection:"column", gap:16 }}>
        <div style={{ width:50, height:50, border:"4px solid #e2e8f0", borderTop:"4px solid #6366f1", borderRadius:"50%", animation:"spin 1s linear infinite" }}/>
        <div style={{ fontSize:15, color:T.slate, fontWeight:600 }}>Loading cases from database...</div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div style={{ fontFamily:"'Segoe UI', system-ui, sans-serif", background:T.bg, minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center", flexDirection:"column", gap:16 }}>
        <div style={{ width:60, height:60, borderRadius:"50%", background:"#fee2e2", display:"flex", alignItems:"center", justifyContent:"center" }}>
          <Icon.AlertTriangle size={30} color="#dc2626"/>
        </div>
        <div style={{ fontSize:18, color:T.navy, fontWeight:700 }}>Failed to Load Cases</div>
        <div style={{ fontSize:14, color:T.slate, maxWidth:400, textAlign:"center" }}>{error}</div>
        <button
          onClick={() => window.location.reload()}
          style={{ background:T.indigo, color:"#fff", border:"none", borderRadius:8, padding:"10px 20px", fontSize:14, fontWeight:600, cursor:"pointer", marginTop:8 }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={{ fontFamily:"'Segoe UI', system-ui, sans-serif", background:T.bg, minHeight:"100vh", display:"flex", flexDirection:"column", fontSize:14, color:T.navyMid }}>

      {/* ── Nav ── */}
      <nav style={{ background:`linear-gradient(135deg, ${T.navy} 0%, ${T.navyMid} 100%)`, color:"#fff", padding:"11px 24px", display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0 }}>
        <div style={{ display:"flex", alignItems:"center", gap:14 }}>
          <div style={{ background:"linear-gradient(135deg,#6366f1,#8b5cf6)", width:36, height:36, borderRadius:10, display:"flex", alignItems:"center", justifyContent:"center" }}>
            <Icon.Shield size={20} color="#fff"/>
          </div>
          <div>
            <div style={{ fontWeight:700, fontSize:15 }}>Singapore Children's Society</div>
            <div style={{ fontSize:10, color:"#94a3b8", letterSpacing:"1.2px", textTransform:"uppercase" }}>YOUTH<sup>TH</sup>CARE · Admin Console</div>
          </div>
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          {/* Data freshness */}
          <div style={{ display:"flex", alignItems:"center", gap:8, background:"rgba(255,255,255,0.07)", border:"1px solid rgba(255,255,255,0.12)", borderRadius:9, padding:"6px 12px" }}>
            <Icon.RefreshCw size={12} color="#94a3b8"/>
            <div>
              <div style={{ fontSize:10, fontWeight:700, color:"#94a3b8", letterSpacing:"0.5px" }}>LAST INGESTION</div>
              <div style={{ fontSize:11, color:"#64748b" }}>Today, 06:00 · Next in ~3h 45m</div>
            </div>
          </div>

          {/* Admin badge */}
          <div style={{ display:"flex", alignItems:"center", gap:8, background:"rgba(255,255,255,0.08)", padding:"5px 12px", borderRadius:20, border:"1px solid rgba(255,255,255,0.15)" }}>
            <Avatar initials={currentUser.avatar_initials} size={26}/>
            <div>
              <div style={{ fontSize:13, fontWeight:600 }}>{currentUser.name}</div>
              <div style={{ fontSize:10, color:"#94a3b8" }}>{currentUser.employee_id} · {currentUser.role}</div>
            </div>
          </div>

          <button onClick={logout} title="Sign out" style={{ display:"flex", alignItems:"center", gap:6, background:"rgba(255,255,255,0.08)", border:"1px solid rgba(255,255,255,0.15)", color:"#94a3b8", borderRadius:9, padding:"7px 12px", fontSize:12, cursor:"pointer" }}
            onMouseEnter={e=>{e.currentTarget.style.color="#fff";e.currentTarget.style.background="rgba(255,255,255,0.14)";}}
            onMouseLeave={e=>{e.currentTarget.style.color="#94a3b8";e.currentTarget.style.background="rgba(255,255,255,0.08)";}}>
            <Icon.LogOut size={14}/> Sign out
          </button>
        </div>
      </nav>

      {/* ── Privacy notice ── */}
      <div style={{ background:"#eef2ff", borderBottom:`1px solid #c7d2fe`, padding:"6px 24px", fontSize:11.5, color:"#4338ca", display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
        <Icon.Lock size={12} color="#4338ca"/>
        <strong>Admin View:</strong> Full case access enabled. All actions are logged for audit purposes. Original social media content is never stored.
      </div>

      {/* ── Body ── */}
      <div style={{ flex:1, display:"flex", overflow:"hidden" }}>

        {/* ── Left: Tabs + Table ── */}
        <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>

          {/* Tab bar */}
          <div style={{ background:"#fff", borderBottom:`1px solid ${T.border}`, padding:"0 20px", display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0 }}>
            <div style={{ display:"flex" }}>
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => { setActiveTab(tab.id); setSelectedCase(null); }}
                  style={{ display:"flex", alignItems:"center", gap:6, padding:"13px 16px", background:"none", border:"none", cursor:"pointer", fontSize:13, fontWeight:activeTab===tab.id?700:500, color:activeTab===tab.id?T.indigo:"#64748b", borderBottom:activeTab===tab.id?`3px solid ${T.indigo}`:"3px solid transparent", transition:"all 0.2s", whiteSpace:"nowrap" }}
                >
                  <span style={{ color:activeTab===tab.id?T.indigo:"#94a3b8" }}>{tab.icon}</span>
                  {tab.label}
                  {tab.count > 0 && (
                    <span style={{ background:tab.id==="review"||tab.id==="unassigned"?"#fee2e2":"#e0e7ff", color:tab.id==="review"||tab.id==="unassigned"?"#991b1b":"#4338ca", borderRadius:10, padding:"1px 7px", fontSize:10, fontWeight:700 }}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Search */}
            {activeTab !== "reassignment" && (
              <div style={{ display:"flex", alignItems:"center", gap:8, background:T.bg, border:`1px solid ${T.border}`, borderRadius:9, padding:"6px 12px", marginLeft:12 }}>
                <Icon.Search size={14} color={T.muted}/>
                <input
                  value={search}
                  onChange={e=>setSearch(e.target.value)}
                  placeholder="Search cases…"
                  style={{ background:"none", border:"none", outline:"none", fontSize:13, color:T.navyMid, width:180 }}
                />
              </div>
            )}
          </div>

          {/* ── Summary stats bar ── */}
          {activeTab !== "reassignment" && (
            <div style={{ background:"#fff", borderBottom:`1px solid ${T.border}`, padding:"8px 20px", display:"flex", gap:20, flexShrink:0 }}>
              {[
                { label:"Total",    val:allCases.length,                             color:T.indigo  },
                { label:"Critical", val:allCases.filter(c=>(c.risk_score||c.riskLevel)===5).length, color:"#dc2626" },
                { label:"High",     val:allCases.filter(c=>(c.risk_score||c.riskLevel)===4).length, color:"#f97316" },
                { label:"Unassigned",val:unassignedCases.length,                     color:"#f59e0b" },
                { label:"Needs Review",val:needsReviewCases.length,                  color:"#9333ea" },
              ].map(s => (
                <div key={s.label} style={{ display:"flex", alignItems:"center", gap:6 }}>
                  <span style={{ fontWeight:700, fontSize:16, color:s.color }}>{s.val}</span>
                  <span style={{ fontSize:11, color:T.muted }}>{s.label}</span>
                </div>
              ))}
            </div>
          )}

          {/* ── Table / Reassignment content ── */}
          <div style={{ flex:1, overflowY:"auto" }}>

            {activeTab !== "reassignment" ? (
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead style={{ position:"sticky", top:0, zIndex:1 }}>
                  <tr>
                    <ColHeader col="case_id"     label="Case ID"   />
                    <ColHeader col="user_id"     label="Youth ID"  />
                    <ColHeader col="riskLevel"   label="Risk"      />
                    <ColHeader col="category"    label="Category"  />
                    <ColHeader col="case_status" label="Case Status" />
                    <ColHeader col="work_status" label="Work Status" />
                    <ColHeader col="assigned_to" label="Assigned To" />
                    <ColHeader col="lastSignal"  label="Last Signal"/>
                    <th style={{ padding:"9px 12px", fontSize:11, fontWeight:700, color:T.muted, textTransform:"uppercase", letterSpacing:"0.6px", background:"#f8fafc", borderBottom:`1px solid ${T.border}`, width:110 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {activeCases().length === 0 ? (
                    <tr><td colSpan={9} style={{ padding:40, textAlign:"center", color:T.muted, fontSize:14 }}>
                      <Icon.CheckCircle size={28} color="#10b981" style={{ display:"block", margin:"0 auto 8px" }}/>
                      No cases in this view.
                    </td></tr>
                  ) : activeCases().map(c => (
                    <CaseRow key={c.case_id||c.code} c={c} showAssignBtn={activeTab==="unassigned"||activeTab==="all"} />
                  ))}
                </tbody>
              </table>
            ) : (
              // ── Reassignment Requests ──────────────────────────────────────
              <div style={{ padding:20, display:"flex", flexDirection:"column", gap:14 }}>
                {reassignments.length === 0 ? (
                  <div style={{ textAlign:"center", marginTop:60, color:T.muted }}>
                    <Icon.CheckCircle size={36} color="#10b981" style={{ display:"block", margin:"0 auto 8px" }}/>
                    <div style={{ fontWeight:600 }}>No pending reassignment requests</div>
                  </div>
                ) : reassignments.map(r => {
                  const caseRow = cases.find(c => (c.case_id||c.code) === r.case_id);
                  const requesterHelper = helpers.find(h => h.user_id === r.requested_by);
                  const targetHelper = r.requested_to ? helpers.find(h => h.user_id === r.requested_to) : null;
                  const statusCfg = { pending:{ bg:"#fffbeb",text:"#92400e",dot:"#f59e0b" }, approved:{ bg:"#ecfdf5",text:"#065f46",dot:"#10b981" }, rejected:{ bg:"#fef2f2",text:"#991b1b",dot:"#dc2626" } }[r.status]||{};
                  return (
                    <div key={r.id} style={{ background:"#fff", border:`1px solid ${T.border}`, borderRadius:12, padding:18, boxShadow:"0 1px 3px rgba(0,0,0,0.05)" }}>
                      <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", marginBottom:12 }}>
                        <div>
                          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
                            <span style={{ fontWeight:700, fontSize:13, color:T.navyMid, fontFamily:"monospace" }}>{r.case_id}</span>
                            {caseRow && <RiskBadge level={caseRow.riskLevel||caseRow.risk_score} score={caseRow.current_risk_score || caseRow.risk_score}/>}
                            {caseRow && <StatusBadge status={caseRow.status}/>}
                          </div>
                          <div style={{ fontSize:11, color:T.muted }}>
                            Requested {new Date(r.created_at).toLocaleDateString("en-SG",{day:"2-digit",month:"short",year:"numeric"})}
                          </div>
                        </div>
                        <span style={{ display:"inline-flex", alignItems:"center", gap:5, background:statusCfg.bg, color:statusCfg.text, padding:"3px 10px", borderRadius:20, fontSize:11, fontWeight:600 }}>
                          <span style={{ width:5,height:5,borderRadius:"50%",background:statusCfg.dot }}/>
                          {r.status.charAt(0).toUpperCase()+r.status.slice(1)}
                        </span>
                      </div>

                      <div style={{ display:"flex", gap:16, marginBottom:12, flexWrap:"wrap" }}>
                        <div style={{ fontSize:12 }}>
                          <span style={{ color:T.muted }}>From: </span>
                          <strong>{requesterHelper?.name||r.requested_by}</strong>
                          {requesterHelper && <span style={{ color:T.muted }}> ({requesterHelper.employee_id})</span>}
                        </div>
                        <div style={{ fontSize:12 }}>
                          <span style={{ color:T.muted }}>Suggested to: </span>
                          <strong>{targetHelper?.name||r.requested_to||"Any available helper"}</strong>
                        </div>
                      </div>

                      <div style={{ background:"#f8fafc", border:`1px solid ${T.border}`, borderRadius:8, padding:"10px 12px", marginBottom:12 }}>
                        <div style={{ fontSize:10, fontWeight:700, color:T.muted, textTransform:"uppercase", letterSpacing:"0.7px", marginBottom:4 }}>Reason</div>
                        <div style={{ fontSize:13, color:T.slate, lineHeight:1.5 }}>{r.reason}</div>
                      </div>

                      {r.status === "pending" && (
                        <div style={{ display:"flex", gap:8 }}>
                          <button
                            onClick={() => handleReassignAction(r.id, "approved", r.requested_to)}
                            style={{ display:"flex", alignItems:"center", gap:6, background:"#10b981", color:"#fff", border:"none", borderRadius:8, padding:"7px 16px", fontSize:12, fontWeight:600, cursor:"pointer" }}
                          >
                            <Icon.Check size={13} color="#fff"/> Approve
                          </button>
                          <button
                            onClick={() => handleReassignAction(r.id, "rejected")}
                            style={{ display:"flex", alignItems:"center", gap:6, background:"#fef2f2", color:"#dc2626", border:"1px solid #fecaca", borderRadius:8, padding:"7px 16px", fontSize:12, fontWeight:600, cursor:"pointer" }}
                          >
                            <Icon.X size={13} color="#dc2626"/> Reject
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: Case detail slide-in ── */}
        {selectedCase && (
          <AdminCaseDetail
            c={selectedCase}
            helpers={helpers}
            currentUser={currentUser}
            onClose={() => setSelectedCase(null)}
            onAssign={handleAssignment}
          />
        )}
      </div>

      {/* ── Assignment modal ── */}
      {assignModal && (
        <AssignModal
          caseRow={assignModal}
          helpers={helpers}
          currentUser={currentUser}
          onConfirm={handleAssignment}
          onClose={() => setAssignModal(null)}
        />
      )}
    </div>
  );
}
