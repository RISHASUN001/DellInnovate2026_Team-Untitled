// Content script runs on Instagram pages
// Responsible for extracting visible content from the DOM

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "extractContent") {
    const content = extractInstagramContent();
    sendResponse(content);
    return;
  }

  if (request.action === "toggleSidePanel") {
    togglePanel();
    sendResponse({ ok: true, visible: panelVisible });
  }
});

const PANEL_ID = "yrpa-side-panel";
const PANEL_STYLE_ID = "yrpa-side-panel-style";
const PANEL_WIDTH_DESKTOP = 420;
const PANEL_WIDTH_SMALL = 360;

let originalBodyMarginRight = "";
let panelVisible = false;

/**
 * Extract all visible content from Instagram profile
 * Returns object with profile info, captions, comments, and image descriptions
 */
function extractInstagramContent() {
  const content = {
    profileBio: extractProfileBio(),
    posts: extractPostsContent(),
    visibleComments: extractVisibleComments(),
    pageUrl: window.location.href,
    extractedAt: new Date().toISOString(),
  };

  return content;
}

/**
 * Extract profile bio from header
 */
function extractProfileBio() {
  let bio = "";

  // Try common Instagram profile bio selectors
  const bioSelectors = [
    "header section span",
    '[data-testid="bio"]',
    "main header span",
    "h2 + div span",
  ];

  for (const selector of bioSelectors) {
    const element = document.querySelector(selector);
    if (element) {
      const text = element.textContent.trim();
      if (text && text.length > 0) {
        bio = text;
        break;
      }
    }
  }

  return bio;
}

/**
 * Extract captions and metadata from visible posts
 */
function extractPostsContent() {
  const posts = [];
  const postElements = document.querySelectorAll("article");

  postElements.forEach((article, index) => {
    if (posts.length >= 20) return; // Limit to first 20 posts visible

    const post = {
      index: index,
      caption: extractCaption(article),
      altTexts: extractImageAltTexts(article),
      links: extractPostLinks(article),
    };

    // Only add if we have content
    if (post.caption || post.altTexts.length > 0) {
      posts.push(post);
    }
  });

  return posts;
}

/**
 * Extract caption text from a post article element
 */
function extractCaption(article) {
  let caption = "";

  // Try to find caption text near the article
  const captionSelectors = [
    'span[data-testid="post-text"]',
    "span h1",
    "article span:nth-of-type(1)",
    'div[role="menuitem"] span',
  ];

  for (const selector of captionSelectors) {
    const element = article.querySelector(selector);
    if (element) {
      const text = element.textContent.trim();
      if (text && text.length > 0) {
        caption = text;
        break;
      }
    }
  }

  // Fallback: get all text from article and filter
  if (!caption) {
    const allText = article.innerText;
    // Remove common Instagram UI text
    const filtered = allText
      .split("\n")
      .filter((line) => line.length > 5 && !line.includes("Like"))
      .slice(0, 2)
      .join(" ");
    caption = filtered;
  }

  return caption;
}

/**
 * Extract alt text from images (important for accessibility and content description)
 */
function extractImageAltTexts(article) {
  const altTexts = [];
  const images = article.querySelectorAll("img");

  images.forEach((img) => {
    if (img.alt && img.alt.trim().length > 0) {
      altTexts.push(img.alt);
    }
  });

  return altTexts;
}

/**
 * Extract links and hashtags from post
 */
function extractPostLinks(article) {
  const links = [];
  const anchors = article.querySelectorAll("a");

  anchors.forEach((anchor) => {
    const href = anchor.getAttribute("href");
    const text = anchor.textContent.trim();

    // Capture hashtags and mentions
    if ((text.startsWith("#") || text.startsWith("@")) && text.length > 1) {
      links.push(text);
    }
  });

  return links;
}

/**
 * Extract visible comments from the current view
 * Note: Comments are lazy-loaded on Instagram, so we only get currently visible ones
 */
function extractVisibleComments() {
  const comments = [];
  const commentSelectors = [
    '[data-testid="comment"]',
    'div[role="article"] span[aria-label*="comment"]',
    "ul li div span",
  ];

  // Try different selectors
  for (const selector of commentSelectors) {
    const elements = document.querySelectorAll(selector);
    if (elements.length > 0) {
      elements.forEach((element) => {
        const text = element.textContent.trim();
        // Filter for meaningful comments (not too short)
        if (
          text.length > 5 &&
          text.length < 500 &&
          !text.includes("View replies")
        ) {
          // Remove duplicate comments
          if (!comments.includes(text)) {
            comments.push(text);
          }
        }
      });
      break;
    }
  }

  // Limit to first 50 visible comments
  return comments.slice(0, 50);
}

function getPanelWidth() {
  return window.innerWidth < 1200 ? PANEL_WIDTH_SMALL : PANEL_WIDTH_DESKTOP;
}

function applyBodyOffset() {
  const width = getPanelWidth();
  document.body.style.marginRight = `${width}px`;
}

function restoreBodyOffset() {
  document.body.style.marginRight = originalBodyMarginRight;
}

function injectPanelStyles() {
  if (document.getElementById(PANEL_STYLE_ID)) return;

  const style = document.createElement("style");
  style.id = PANEL_STYLE_ID;
  style.textContent = `
    #${PANEL_ID} {
      position: fixed;
      top: 0;
      right: 0;
      height: 100vh;
      width: ${PANEL_WIDTH_DESKTOP}px;
      z-index: 999999;
      display: flex;
      flex-direction: column;
      background: #fff;
      box-shadow: -6px 0 20px rgba(0,0,0,0.15);
      border-left: 1px solid #e8ecf3;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      color: #1f2937;
    }

    #${PANEL_ID} .panel-header {
      flex-shrink: 0;
      padding: 14px 16px;
      border-bottom: 1px solid #e5e7eb;
      background: linear-gradient(135deg, #0a1628 0%, #0f172a 100%);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    #${PANEL_ID} .panel-header-left {
      min-width: 0;
    }

    #${PANEL_ID} .panel-close {
      width: 30px;
      height: 30px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.25);
      background: rgba(255,255,255,0.1);
      color: #fff;
      font-size: 16px;
      line-height: 1;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    #${PANEL_ID} .panel-close:hover {
      background: rgba(255,255,255,0.18);
    }

    #${PANEL_ID} .panel-title {
      font-size: 14px;
      font-weight: 700;
      color: #fff;
    }

    #${PANEL_ID} .panel-subtitle {
      font-size: 11px;
      color: #94a3b8;
      margin-top: 2px;
    }

    #${PANEL_ID} .panel-content {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      background: #f8fafc;
    }

    #${PANEL_ID} .card {
      width: 100%;
      border-radius: 12px;
      padding: 16px;
      box-sizing: border-box;
      border: 1px solid #e2e8f0;
      background: #fff;
      box-shadow: 0 1px 3px rgba(60,64,67,0.12);
    }

    #${PANEL_ID} .card-title {
      font-size: 13px;
      font-weight: 700;
      color: #1e293b;
      margin-bottom: 10px;
    }

    #${PANEL_ID} .field {
      margin-bottom: 10px;
    }

    #${PANEL_ID} .field:last-child {
      margin-bottom: 0;
    }

    #${PANEL_ID} .field label {
      display: block;
      font-size: 11px;
      font-weight: 600;
      color: #4b5563;
      margin-bottom: 5px;
    }

    #${PANEL_ID} .field input {
      width: 100%;
      border: 1px solid #d8dee9;
      border-radius: 8px;
      padding: 9px 10px;
      font-size: 12px;
      outline: none;
      background: #fff;
      color: #111827;
    }

    #${PANEL_ID} .field input:focus {
      border-color: #0672CB;
      box-shadow: 0 0 0 2px rgba(6, 114, 203, 0.14);
    }

    #${PANEL_ID} .button {
      width: 100%;
      padding: 12px;
      border-radius: 8px;
      border: 1px solid transparent;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      margin-top: 8px;
    }

    #${PANEL_ID} .button:first-of-type {
      margin-top: 0;
    }

    #${PANEL_ID} .button-primary {
      background: linear-gradient(135deg, #0672CB 0%, #0460a9 100%);
      color: #fff;
      box-shadow: 0 1px 3px rgba(6,114,203,0.22);
    }

    #${PANEL_ID} .button-analyze {
      background: linear-gradient(135deg, #0672CB 0%, #0460a9 100%);
      color: #fff;
      box-shadow: 0 1px 3px rgba(6,114,203,0.22);
    }

    #${PANEL_ID} .button-capture {
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
      color: #fff;
      box-shadow: 0 1px 3px rgba(16,185,129,0.22);
    }

    #${PANEL_ID} .button-secondary {
      background: #f1f5f9;
      color: #64748b;
      border-color: #e2e8f0;
    }

    #${PANEL_ID} .button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      box-shadow: none;
    }

    #${PANEL_ID} .risk-row {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    #${PANEL_ID} .risk-indicator {
      width: 48px;
      height: 48px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: 700;
      color: #fff;
      flex-shrink: 0;
    }

    #${PANEL_ID} .risk-low { background: #16a34a; }
    #${PANEL_ID} .risk-medium { background: #d97706; }
    #${PANEL_ID} .risk-high { background: #ea580c; }
    #${PANEL_ID} .risk-critical { background: #dc2626; }
    #${PANEL_ID} .risk-unknown { background: #64748b; }

    #${PANEL_ID} .risk-text {
      font-size: 18px;
      font-weight: 700;
      color: #111827;
    }

    #${PANEL_ID} .list {
      max-height: 180px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    #${PANEL_ID} .list-item {
      border-left: 2px solid #0672CB;
      background: #f8fafc;
      border-radius: 8px;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.5;
      word-break: break-word;
    }

    #${PANEL_ID} .list-item.comment {
      border-left-color: #f59e0b;
      background: #fffaf0;
    }

    #${PANEL_ID} .muted {
      font-size: 12px;
      color: #6b7280;
      font-style: italic;
    }

    #${PANEL_ID} .message {
      font-size: 12px;
      color: #065f46;
      background: #ecfdf5;
      border: 1px solid #a7f3d0;
      border-radius: 8px;
      padding: 8px 10px;
      display: none;
    }

    #${PANEL_ID} .error {
      font-size: 12px;
      color: #991b1b;
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 8px;
      padding: 10px;
      display: none;
    }

    #${PANEL_ID} .loading {
      font-size: 12px;
      color: #4b5563;
      display: none;
    }

    @media (max-width: 1200px) {
      #${PANEL_ID} {
        width: ${PANEL_WIDTH_SMALL}px;
      }
    }
  `;

  document.head.appendChild(style);
}

function buildPanelHtml() {
  return `
    <div class="panel-header">
      <div class="panel-header-left">
        <div class="panel-title">CaptchaGram!</div>
      </div>
      <button id="yrpa-close" class="panel-close" aria-label="Close panel" title="Close">×</button>
    </div>

    <div class="panel-content">
      <div class="card" id="yrpa-settings-card">
        <div class="card-title">API Config</div>
        <div class="field">
          <label for="yrpa-api-key">OpenAI API Key</label>
          <input id="yrpa-api-key" type="password" placeholder="sk-proj-..." />
        </div>
        <div class="field">
          <label for="yrpa-org-id">Organization ID (Optional)</label>
          <input id="yrpa-org-id" type="text" placeholder="org-..." />
        </div>
        <button id="yrpa-save-settings" class="button button-primary">Save Settings</button>
        <div id="yrpa-settings-msg" class="message"></div>
      </div>

      <div class="card">
        <div class="card-title">Analyze Buttons</div>
        <button id="yrpa-analyze" class="button button-analyze" disabled>Analyze Profile & Content</button>
        <button id="yrpa-capture" class="button button-capture" disabled>Capture & Analyze Screen</button>
        <button id="yrpa-clear" class="button button-secondary">Clear Results</button>
      </div>

      <div id="yrpa-loading" class="card loading">Analyzing content...</div>

      <div id="yrpa-results" style="display:none;">
        <div class="card">
          <div class="card-title">Risk Assessment</div>
          <div class="risk-row">
            <div id="yrpa-risk-indicator" class="risk-indicator risk-unknown"></div>
            <div id="yrpa-risk-text" class="risk-text">UNKNOWN</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Signals</div>
          <div id="yrpa-signals" class="list"><div class="muted">No signals detected</div></div>
        </div>

        <div class="card">
          <div class="card-title">Comments</div>
          <div id="yrpa-comments" class="list"><div class="muted">No flagged comments</div></div>
        </div>

        <div class="card">
          <div class="card-title">Summary</div>
          <div id="yrpa-summary" class="muted">No summary available</div>
        </div>
      </div>

      <div id="yrpa-error" class="error"></div>
    </div>
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showPanelMessage(panel, message, isError = false) {
  const msg = panel.querySelector("#yrpa-settings-msg");
  msg.textContent = message;
  msg.style.display = "block";
  msg.style.color = isError ? "#991b1b" : "#065f46";
  msg.style.background = isError ? "#fef2f2" : "#ecfdf5";
  msg.style.borderColor = isError ? "#fecaca" : "#a7f3d0";

  setTimeout(() => {
    msg.style.display = "none";
  }, 2400);
}

function clearPanelResults(panel) {
  panel.querySelector("#yrpa-results").style.display = "none";
  panel.querySelector("#yrpa-error").style.display = "none";
  panel.querySelector("#yrpa-loading").style.display = "none";
}

function showPanelError(panel, message) {
  const error = panel.querySelector("#yrpa-error");
  error.textContent = message;
  error.style.display = "block";
}

function renderPanelResults(panel, analysis) {
  const results = panel.querySelector("#yrpa-results");
  results.style.display = "block";
  panel.querySelector("#yrpa-error").style.display = "none";

  const riskLevel = (analysis?.risk_level || "UNKNOWN").toUpperCase();
  const indicator = panel.querySelector("#yrpa-risk-indicator");
  const riskText = panel.querySelector("#yrpa-risk-text");
  riskText.textContent = riskLevel;
  indicator.className = `risk-indicator risk-${riskLevel.toLowerCase()}`;

  const signals = panel.querySelector("#yrpa-signals");
  const signalItems = Array.isArray(analysis?.signals_detected)
    ? analysis.signals_detected
    : [];
  if (signalItems.length > 0) {
    signals.innerHTML = signalItems
      .map((signal) => `<div class="list-item">• ${escapeHtml(signal)}</div>`)
      .join("");
  } else {
    signals.innerHTML = '<div class="muted">No signals detected</div>';
  }

  const comments = panel.querySelector("#yrpa-comments");
  const commentItems = Array.isArray(analysis?.flagged_comments)
    ? analysis.flagged_comments
    : [];
  if (commentItems.length > 0) {
    comments.innerHTML = commentItems
      .map(
        (comment) => `<div class="list-item comment">"${escapeHtml(comment)}"</div>`,
      )
      .join("");
  } else {
    comments.innerHTML = '<div class="muted">No flagged comments</div>';
  }

  const summary = panel.querySelector("#yrpa-summary");
  if (analysis?.summary) {
    summary.className = "";
    summary.style.fontSize = "12px";
    summary.style.lineHeight = "1.6";
    summary.style.color = "#374151";
    summary.textContent = analysis.summary;
  } else {
    summary.className = "muted";
    summary.textContent = "No summary available";
  }
}

async function getStoredSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["apiKey", "orgId"], resolve);
  });
}

async function captureScreenshotForCurrentTab() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ action: "captureVisibleTab" }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }

      if (!response?.ok || !response?.dataUrl) {
        reject(new Error(response?.error || "Unable to capture screen"));
        return;
      }

      resolve(response.dataUrl);
    });
  });
}

async function runAnalysis(panel, downloadScreenshot = false) {
  clearPanelResults(panel);
  const loading = panel.querySelector("#yrpa-loading");
  loading.style.display = "block";

  try {
    const { apiKey, orgId } = await getStoredSettings();
    if (!apiKey) {
      throw new Error("API key not configured. Save API settings first.");
    }

    const screenshot = await captureScreenshotForCurrentTab();

    if (downloadScreenshot) {
      const link = document.createElement("a");
      link.href = screenshot;
      link.download = `instagram-capture-${Date.now()}.png`;
      link.click();
    }

    const extractedContent = extractInstagramContent();

    if (typeof analyzeWithOpenAI !== "function") {
      throw new Error("OpenAI analyzer not available in content context.");
    }

    const analysis = await analyzeWithOpenAI(
      screenshot,
      extractedContent,
      apiKey,
      orgId,
    );

    renderPanelResults(panel, analysis);
  } catch (error) {
    showPanelError(panel, error.message || "Failed to analyze content");
  } finally {
    loading.style.display = "none";
  }
}

function wirePanelEvents(panel) {
  const apiKeyInput = panel.querySelector("#yrpa-api-key");
  const orgIdInput = panel.querySelector("#yrpa-org-id");
  const saveBtn = panel.querySelector("#yrpa-save-settings");
  const analyzeBtn = panel.querySelector("#yrpa-analyze");
  const captureBtn = panel.querySelector("#yrpa-capture");
  const clearBtn = panel.querySelector("#yrpa-clear");
  const closeBtn = panel.querySelector("#yrpa-close");

  const syncButtonState = () => {
    const hasApiKey = !!apiKeyInput.value.trim();
    analyzeBtn.disabled = !hasApiKey;
    captureBtn.disabled = !hasApiKey;
  };

  getStoredSettings().then(({ apiKey, orgId }) => {
    apiKeyInput.value = apiKey || "";
    orgIdInput.value = orgId || "";
    syncButtonState();
  });

  apiKeyInput.addEventListener("input", syncButtonState);

  saveBtn.addEventListener("click", () => {
    const apiKey = apiKeyInput.value.trim();
    const orgId = orgIdInput.value.trim();
    if (!apiKey) {
      showPanelMessage(panel, "Please enter a valid API key", true);
      syncButtonState();
      return;
    }

    chrome.storage.local.set({ apiKey, orgId }, () => {
      syncButtonState();
      showPanelMessage(panel, "Settings saved");
    });
  });

  analyzeBtn.addEventListener("click", () => runAnalysis(panel, false));
  captureBtn.addEventListener("click", () => runAnalysis(panel, true));
  clearBtn.addEventListener("click", () => clearPanelResults(panel));
  closeBtn.addEventListener("click", hidePanel);
}

function createSidePanel() {
  if (document.getElementById(PANEL_ID)) return;

  originalBodyMarginRight = document.body.style.marginRight || "";

  injectPanelStyles();

  const panel = document.createElement("aside");
  panel.id = PANEL_ID;
  panel.innerHTML = buildPanelHtml();
  panel.style.display = "none";
  document.body.appendChild(panel);
  wirePanelEvents(panel);

  window.addEventListener("resize", () => {
    if (panelVisible) {
      applyBodyOffset();
    }
  });
  window.addEventListener("beforeunload", restoreBodyOffset);
}

function showPanel() {
  const panel = document.getElementById(PANEL_ID);
  if (!panel) return;
  panel.style.display = "flex";
  panelVisible = true;
  applyBodyOffset();
}

function hidePanel() {
  const panel = document.getElementById(PANEL_ID);
  if (!panel) return;
  panel.style.display = "none";
  panelVisible = false;
  restoreBodyOffset();
}

function togglePanel() {
  if (!document.getElementById(PANEL_ID)) {
    createSidePanel();
  }

  if (panelVisible) {
    hidePanel();
  } else {
    showPanel();
  }
}

if (window.top === window && location.hostname.includes("instagram.com")) {
  createSidePanel();
}

console.log("Instagram Content Extractor and right-side panel loaded");
