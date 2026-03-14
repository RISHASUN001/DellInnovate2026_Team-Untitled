// UI Element References
const apiKeyInput = document.getElementById("apiKey");
const orgIdInput = document.getElementById("orgId");
const toggleApiKeyBtn = document.getElementById("toggleApiKey");
const saveSettingsBtn = document.getElementById("saveSettingsBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const captureScreenBtn = document.getElementById("captureScreenBtn");
const clearBtn = document.getElementById("clearBtn");
const settingsMessage = document.getElementById("settingsMessage");
const loadingState = document.getElementById("loadingState");
const resultsSection = document.getElementById("resultsSection");
const errorSection = document.getElementById("errorSection");
const settingsSection = document.getElementById("settingsSection");

let currentAnalysisData = null;

// Initialize on popup load
document.addEventListener("DOMContentLoaded", async () => {
  await loadStoredSettings();
  updateButtonStates();
});

// Load stored API settings
async function loadStoredSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["apiKey", "orgId"], (result) => {
      if (result.apiKey) {
        apiKeyInput.value = result.apiKey;
        analyzeBtn.disabled = false;
        captureScreenBtn.disabled = false;
      }
      if (result.orgId) {
        orgIdInput.value = result.orgId;
      }
      resolve();
    });
  });
}

// Toggle API key visibility
toggleApiKeyBtn.addEventListener("click", () => {
  const type = apiKeyInput.type === "password" ? "text" : "password";
  apiKeyInput.type = type;
  toggleApiKeyBtn.textContent = type === "password" ? "Show" : "Hide";
});

// Save API settings
saveSettingsBtn.addEventListener("click", () => {
  const apiKey = apiKeyInput.value.trim();
  const orgId = orgIdInput.value.trim();

  if (!apiKey) {
    showMessage(settingsMessage, "Please enter a valid API key", "error");
    return;
  }

  chrome.storage.local.set({ apiKey, orgId }, () => {
    showMessage(settingsMessage, "Settings saved successfully", "success");
    updateButtonStates();
  });
});

// Analyze current profile
analyzeBtn.addEventListener("click", async () => {
  console.log("=== Analyze button clicked ===");
  clearResults();
  showLoading(true);

  try {
    console.log("Getting active tab...");
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    console.log("Active tab:", tab.url);

    // Capture screenshot
    console.log("Capturing screenshot...");
    const screenshot = await chrome.tabs.captureVisibleTab(tab.windowId);
    console.log("Screenshot captured, length:", screenshot?.length || 0);
    console.log("Screenshot preview:", screenshot?.substring(0, 50));

    // Extract content from Instagram page with fallback
    let extractedContent = {
      profileBio: "",
      posts: [],
      visibleComments: [],
      pageUrl: tab.url,
      extractedAt: new Date().toISOString(),
    };

    try {
      console.log("Sending extractContent message...");
      const result = await chrome.tabs.sendMessage(tab.id, {
        action: "extractContent",
      });
      if (result) {
        extractedContent = result;
        console.log("Content extracted successfully");
      }
    } catch (e) {
      console.log(
        "Content extraction failed (will continue with empty content):",
        e.message,
      );
    }

    // Get stored API key
    console.log("Retrieving stored API key...");
    const { apiKey, orgId } = await new Promise((resolve) => {
      chrome.storage.local.get(["apiKey", "orgId"], resolve);
    });

    if (!apiKey) {
      throw new Error("API key not configured");
    }
    console.log("API key found, calling analyzeWithOpenAI...");

    // Send to OpenAI for analysis
    const analysis = await analyzeWithOpenAI(
      screenshot,
      extractedContent,
      apiKey,
      orgId,
    );

    console.log("Analysis result:", analysis);
    currentAnalysisData = analysis;
    displayResults(analysis);
    showLoading(false);
  } catch (error) {
    showLoading(false);
    showError(error.message || "Failed to analyze profile");
    console.error("Analysis error:", error);
  }
});

// Capture screen and analyze (for stories and current view)
captureScreenBtn.addEventListener("click", async () => {
  console.log("=== Capture screen button clicked ===");
  clearResults();
  showLoading(true);

  try {
    console.log("Getting active tab...");
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    console.log("Active tab:", tab.url);

    // Capture screenshot
    console.log("Capturing screenshot...");
    const screenshot = await chrome.tabs.captureVisibleTab(tab.windowId);
    console.log("Screenshot captured, length:", screenshot?.length || 0);
    console.log("Screenshot preview:", screenshot?.substring(0, 50));

    // Save screenshot automatically
    console.log("Saving screenshot...");
    const link = document.createElement("a");
    link.href = screenshot;
    link.download = `instagram-capture-${Date.now()}.png`;
    link.click();
    console.log("Screenshot download triggered");

    // Extract content from Instagram page with fallback
    let extractedContent = {
      profileBio: "",
      posts: [],
      visibleComments: [],
      pageUrl: tab.url,
      extractedAt: new Date().toISOString(),
    };

    try {
      console.log("Sending extractContent message...");
      const result = await chrome.tabs.sendMessage(tab.id, {
        action: "extractContent",
      });
      if (result) {
        extractedContent = result;
        console.log("Content extracted successfully");
      }
    } catch (e) {
      console.log(
        "Content extraction failed (will continue with empty content):",
        e.message,
      );
    }

    // Get stored API key
    console.log("Retrieving stored API key...");
    const { apiKey, orgId } = await new Promise((resolve) => {
      chrome.storage.local.get(["apiKey", "orgId"], resolve);
    });

    if (!apiKey) {
      throw new Error("API key not configured");
    }
    console.log("API key found, calling analyzeWithOpenAI...");

    // Send to OpenAI for analysis
    const analysis = await analyzeWithOpenAI(
      screenshot,
      extractedContent,
      apiKey,
      orgId,
    );

    console.log("Analysis result:", analysis);
    currentAnalysisData = analysis;
    displayResults(analysis);
    showLoading(false);
    showMessage(settingsMessage, "Screenshot saved & analyzed", "success");
  } catch (error) {
    showLoading(false);
    showError(error.message || "Failed to capture and analyze screen");
    console.error("Capture and analysis error:", error);
  }
});

// Clear results
clearBtn.addEventListener("click", () => {
  clearResults();
  showMessage(settingsMessage, "Results cleared", "info");
});

// Display analysis results
function displayResults(analysis) {
  resultsSection.style.display = "block";
  errorSection.style.display = "none";

  // Risk Level
  const riskLevel = analysis.risk_level || "UNKNOWN";
  const riskIndicator = document.getElementById("riskIndicator");
  const riskText = document.getElementById("riskText");

  riskText.textContent = riskLevel;
  riskIndicator.className = "risk-indicator risk-" + riskLevel.toLowerCase();

  // Signals Detected
  const signalsDiv = document.getElementById("signalsDetected");
  if (analysis.signals_detected && analysis.signals_detected.length > 0) {
    signalsDiv.innerHTML = analysis.signals_detected
      .map((signal) => `<div class="signal-item">• ${escapeHtml(signal)}</div>`)
      .join("");
  } else {
    signalsDiv.innerHTML =
      '<p class="no-data">No concerning signals detected</p>';
  }

  // Flagged Comments
  const commentsDiv = document.getElementById("flaggedComments");
  if (analysis.flagged_comments && analysis.flagged_comments.length > 0) {
    commentsDiv.innerHTML = analysis.flagged_comments
      .map(
        (comment) => `<div class="comment-item">"${escapeHtml(comment)}"</div>`,
      )
      .join("");
  } else {
    commentsDiv.innerHTML = '<p class="no-data">No flagged comments</p>';
  }

  // Summary
  const summaryDiv = document.getElementById("summary");
  if (analysis.summary) {
    summaryDiv.innerHTML = `<p>${escapeHtml(analysis.summary)}</p>`;
  } else {
    summaryDiv.innerHTML = '<p class="no-data">No summary available</p>';
  }
}

// Show loading state
function showLoading(show) {
  loadingState.style.display = show ? "block" : "none";
}

// Show error message
function showError(message) {
  errorSection.style.display = "block";
  resultsSection.style.display = "none";
  document.getElementById("errorMessage").textContent = message;
}

// Show temporary message
function showMessage(element, message, type) {
  element.textContent = message;
  element.className = "message " + type;
  element.style.display = "block";

  if (type !== "error") {
    setTimeout(() => {
      element.style.display = "none";
    }, 3000);
  }
}

// Clear all results
function clearResults() {
  resultsSection.style.display = "none";
  errorSection.style.display = "none";
  loadingState.style.display = "none";
  currentAnalysisData = null;
}

// Update button states based on API key availability
function updateButtonStates() {
  chrome.storage.local.get(["apiKey"], (result) => {
    const hasApiKey = !!result.apiKey;
    analyzeBtn.disabled = !hasApiKey;
    captureScreenBtn.disabled = !hasApiKey;
  });
}

// Utility: Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
