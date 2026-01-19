// Background script for Video Download Assistant

chrome.runtime.onInstalled.addListener(() => {
  // Set default settings on installation
  chrome.storage.sync.set({
    language: 'en',
    serverPort: 8080,
    downloadFolder: 'Downloads'
  });
});

// Handle messages from content script and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getVideoInfo') {
    // Forward video info request to popup if it's open
    chrome.runtime.sendMessage({
      action: 'videoInfoReceived',
      data: request.data
    }).catch(() => {
      // Popup might not be open, that's ok
    });
  }
});

// Check server connection periodically
let serverCheckInterval;

function startServerCheck() {
  if (serverCheckInterval) {
    clearInterval(serverCheckInterval);
  }
  
  serverCheckInterval = setInterval(async () => {
    try {
      const settings = await chrome.storage.sync.get(['serverPort', 'serveripinput']);
      const port = settings.serverPort || 8080;
      const serverIp = settings.serveripinput || '127.0.0.1';

      const response = await fetch(`http://${serverIp}:${port}/status`);
      if (response.ok) {
        chrome.action.setBadgeText({ text: '●' });
        chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
      } else {
        throw new Error('Server not responding');
      }
    } catch (error) {
      chrome.action.setBadgeText({ text: '●' });
      chrome.action.setBadgeBackgroundColor({ color: '#F44336' });
    }
  }, 5000);
}

// Start checking server status
startServerCheck();

// Listen for storage changes to update server port
chrome.storage.onChanged.addListener((changes) => {
  if (changes.serverPort) {
    startServerCheck();
  }
});
