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
  }
});

// Clean up storage periodically (data retention policy)
// Keep API key indefinitely but clear old analysis logs if needed
chrome.runtime.onStartup.addListener(() => {
  console.log("Extension background worker started");
});

// Handle extension icon click (optional - shows popup by default)
chrome.action.onClicked.addListener((tab) => {
  // If no popup is set, this opens the popup
  console.log("Extension icon clicked on tab:", tab.id);
});
