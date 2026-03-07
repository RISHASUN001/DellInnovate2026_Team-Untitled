/**
 * API Service Layer for SCS Youth Helper Dashboard
 * Handles communication with case-service and API gateway backends.
 */

const CASE_SERVICE_URL = import.meta.env.VITE_CASE_SERVICE_URL || "http://localhost:8003";
const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL || "http://localhost:8010";

// ─── Helper Functions ──────────────────────────────────────────────────────

const getAuthToken = () => {
  const sessionToken = sessionStorage.getItem("scs_auth_token");
  const localToken = localStorage.getItem("scs_auth_token");
  return sessionToken || localToken || "";
};

const buildAuthHeaders = (headers = {}, requireAuth = false) => {
  const merged = { ...headers };
  const token = getAuthToken();

  if (token) {
    merged.Authorization = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
  } else if (requireAuth) {
    throw new Error(
      "Missing auth token. Please login and ensure a valid bearer token is present in sessionStorage/localStorage as 'scs_auth_token'."
    );
  }

  return merged;
};

const handleResponse = async (response) => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "Network error" }));
    throw new Error(error.message || error.error || `HTTP ${response.status}`);
  }
  return response.json();
};

const fetchWithAuth = async (url, options = {}, requireAuth = false) => {
  const finalHeaders = buildAuthHeaders(options.headers, requireAuth);
  const headers = {
    "Content-Type": "application/json",
    ...finalHeaders,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  return handleResponse(response);
};

// ─── Case API ──────────────────────────────────────────────────────────────

export const caseAPI = {
  /**
   * Get all cases (with optional filters)
   */
  async getAllCases(filters = {}) {
    const params = new URLSearchParams();
    
    if (filters.category) params.append("category", filters.category);
    if (filters.case_status) params.append("case_status", filters.case_status);
    if (filters.work_status) params.append("work_status", filters.work_status);
    if (filters.priority) params.append("priority", filters.priority);
    if (filters.assigned_to) params.append("assigned_to", filters.assigned_to);

    const url = `${CASE_SERVICE_URL}/cases?${params.toString()}`;
    return fetchWithAuth(url);
  },

  /**
   * Get unassigned cases (admin only)
   */
  async getUnassignedCases() {
    const url = `${CASE_SERVICE_URL}/cases/unassigned`;
    return fetchWithAuth(url);
  },

  /**
   * Get single case detail
   */
  async getCase(caseId) {
    const url = `${CASE_SERVICE_URL}/cases/${caseId}`;
    return fetchWithAuth(url);
  },

  /**
   * Assign case to helper (admin only)
   */
  async assignCase(caseId, helperId) {
    const url = `${CASE_SERVICE_URL}/cases/${caseId}/assign`;
    return fetchWithAuth(url, {
      method: "POST",
      body: JSON.stringify({ assigned_to: helperId }),
    });
  },

  /**
   * Update case (work status, priority, etc.)
   */
  async updateCase(caseId, updates) {
    const url = `${CASE_SERVICE_URL}/cases/${caseId}`;
    return fetchWithAuth(url, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  },

  /**
   * Get cases by priority (stats)
   */
  async getCasesByPriority() {
    const url = `${CASE_SERVICE_URL}/cases/stats/by-priority`;
    return fetchWithAuth(url);
  },

  /**
   * Get cases by category (stats)
   */
  async getCasesByCategory() {
    const url = `${CASE_SERVICE_URL}/cases/stats/by-category`;
    return fetchWithAuth(url);
  },
};

// ─── User API ──────────────────────────────────────────────────────────────

export const userAPI = {
  /**
   * Get all users (or filter by role)
   */
  async getUsers(role = null) {
    const params = role ? `?role=${role}` : "";
    const url = `${CASE_SERVICE_URL}/users${params}`;
    return fetchWithAuth(url);
  },

  /**
   * Get youth helpers only
   */
  async getYouthHelpers() {
    return this.getUsers("youth_helper");
  },

  /**
   * Get admins only
   */
  async getAdmins() {
    return this.getUsers("admin");
  },
};

// ─── Checklist API ─────────────────────────────────────────────────────────

export const checklistAPI = {
  /**
   * Get checklist for a case
   */
  async getChecklist(caseId) {
    const url = `${CASE_SERVICE_URL}/checklist/${caseId}`;
    return fetchWithAuth(url);
  },

  /**
   * Update checklist item
   */
  async updateItem(caseId, itemId, data) {
    const url = `${CASE_SERVICE_URL}/checklist/${caseId}/items/${itemId}`;
    return fetchWithAuth(url, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  /**
   * Add custom checklist item
   */
  async addItem(caseId, data) {
    const url = `${CASE_SERVICE_URL}/checklist/${caseId}/items`;
    return fetchWithAuth(url, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};

// ─── History API ───────────────────────────────────────────────────────────

export const historyAPI = {
  /**
   * Get case ingestion history (risk progression over time)
   * Returns chronological entries showing how risk score evolved
   */
  async getCaseHistory(caseId, limit = null) {
    const params = limit ? `?limit=${limit}` : "";
    const url = `${CASE_SERVICE_URL}/history/cases/${caseId}${params}`;
    return fetchWithAuth(url);
  },
};

// ─── Utility Functions ─────────────────────────────────────────────────────

/**
 * Transform MongoDB case to frontend format
 */
export const transformCase = (mongoCase) => {
  return {
    id: mongoCase.case_id,
    case_id: mongoCase.case_id,
    code: mongoCase.case_id,
    riskLevel: Math.ceil(mongoCase.current_risk_score / 20), // Convert 0-100 to 1-5
    risk_score: mongoCase.current_risk_score,
    current_risk_score: mongoCase.current_risk_score,
    category: mongoCase.category,
    platform: "Instagram", // Default platform
    lastSignal: mongoCase.updated_at || mongoCase.created_at,
    status: mongoCase.work_status || "new",
    assignedTo: mongoCase.assigned_to || "—",
    assigned_to: mongoCase.assigned_to, // Snake_case version for helper matching
    assignedToMe: false, // Set this in component based on current user
    case_status: mongoCase.case_status,
    work_status: mongoCase.work_status,
    priority: mongoCase.priority,
    needs_review: mongoCase.needs_review || 0,
    created_at: mongoCase.created_at,
    updated_at: mongoCase.updated_at,
    youth: {
      name: mongoCase.user_id.replace(/@|_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
      age: 15, // Default - would need to be in DB
      avatar: "👤",
      handle: mongoCase.user_id,
      instagramUrl: `https://instagram.com/${mongoCase.user_id.replace('@', '')}`,
    },
    signals: extractSignals(mongoCase.ai_explanation),
    summary: mongoCase.ai_explanation || "No explanation available",
    ai_explanation: mongoCase.ai_explanation,
  };
};

/**
 * Extract bullet points from AI explanation text
 */
const extractSignals = (aiExplanation) => {
  if (!aiExplanation) return [];
  
  // Extract lines starting with • or -
  const lines = aiExplanation.split('\n');
  const signals = lines
    .filter(line => line.trim().startsWith('•') || line.trim().startsWith('-'))
    .map(line => line.replace(/^[•\-]\s*/, '').trim())
    .filter(line => line.length > 0);
  
  return signals.length > 0 ? signals.slice(0, 5) : [aiExplanation.split('\n\n')[0]];
};

/**
 * Map MongoDB priority to frontend risk level
 */
export const priorityToRiskLevel = {
  "low": 1,
  "medium": 3,
  "high": 4,
  "critical": 5,
};

/**
 * Map risk level back to priority
 */
export const riskLevelToPriority = {
  1: "low",
  2: "low",
  3: "medium",
  4: "high",
  5: "critical",
};

// ─── Chatbot API ───────────────────────────────────────────────────────────

const CHATBOT_SERVICE_URL = import.meta.env.VITE_CHATBOT_SERVICE_URL || "http://localhost:8000";

export const chatbotAPI = {
  /**
   * Get AI-generated recommendations for a case
   */
  async getRecommendations(caseInfo) {
    const url = `${CHATBOT_SERVICE_URL}/recommendations`;
    return fetchWithAuth(url, {
      method: "POST",
      body: JSON.stringify({ case_info: caseInfo }),
    });
  },
};

// ─── API Gateway Orchestration API ─────────────────────────────────────────

export const gatewayAPI = {
  async getHealth() {
    const url = `${API_GATEWAY_URL}/health`;
    return fetchWithAuth(url);
  },

  async scrape(username) {
    const url = `${API_GATEWAY_URL}/scrape`;
    return fetchWithAuth(
      url,
      {
        method: "POST",
        body: JSON.stringify({ username }),
      },
      true
    );
  },

  async analyze(username, opts = {}) {
    const url = `${API_GATEWAY_URL}/analyze`;
    return fetchWithAuth(
      url,
      {
        method: "POST",
        body: JSON.stringify({
          username,
          scrape_comments: opts.scrape_comments ?? true,
          export_csv: opts.export_csv ?? true,
        }),
      },
      true
    );
  },

  async runWorkflow(payload) {
    const url = `${API_GATEWAY_URL}/workflow/run`;
    return fetchWithAuth(
      url,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      true
    );
  },

  async runImageProcessing(payload = {}) {
    const url = `${API_GATEWAY_URL}/image`;
    return fetchWithAuth(
      url,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      true
    );
  },

  async chat(payload) {
    const url = `${API_GATEWAY_URL}/chatbot`;
    return fetchWithAuth(
      url,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      true
    );
  },
};

// ─── Default Export ────────────────────────────────────────────────────────

export default {
  caseAPI,
  userAPI,
  checklistAPI,
  historyAPI,
  chatbotAPI,
  gatewayAPI,
  transformCase,
  priorityToRiskLevel,
  riskLevelToPriority,
};
