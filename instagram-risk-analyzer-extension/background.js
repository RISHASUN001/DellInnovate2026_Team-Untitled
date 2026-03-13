/**
 * Background Service Worker
 * Handles persistent functionality and extension lifecycle
 */

// Initialize extension on install
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    console.log("Youth Profile Risk Analyzer extension installed");
    // Could open a setup page here if needed
  } else if (details.reason === "update") {
    console.log("Extension updated");
  }
});

// Handle messages from popup and content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ping") {
    sendResponse({ status: "ok" });
    return;
  }

  if (request.action === "captureVisibleTab") {
    const windowId = sender?.tab?.windowId;

    chrome.tabs.captureVisibleTab(windowId, { format: "png" }, (dataUrl) => {
      if (chrome.runtime.lastError) {
        sendResponse({ ok: false, error: chrome.runtime.lastError.message });
        return;
      }

      sendResponse({ ok: true, dataUrl });
    });

    return true;
  }
});

// Clean up storage periodically (data retention policy)
// Keep API key indefinitely but clear old analysis logs if needed
chrome.runtime.onStartup.addListener(() => {
  console.log("Extension background worker started");
});

// Handle extension icon click (optional - shows popup by default)
chrome.action.onClicked.addListener((tab) => {
  if (!tab?.id || !tab.url?.includes("instagram.com")) {
    console.log("Extension clicked outside Instagram; no panel toggle");
    return;
  }

  chrome.tabs.sendMessage(tab.id, { action: "toggleSidePanel" }, (response) => {
    if (chrome.runtime.lastError) {
      console.warn("Could not toggle side panel:", chrome.runtime.lastError.message);
      return;
    }
    console.log("Side panel toggled:", response?.visible);
  });
});
