// Background service worker - handles data storage and export

const STORAGE_KEY = 'browsing_history';
const MAX_ENTRIES = 500; // Limit to prevent storage overflow

// Initialize storage on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get([STORAGE_KEY], (result) => {
    if (!result[STORAGE_KEY]) {
      chrome.storage.local.set({ [STORAGE_KEY]: [] });
    }
  });
  console.log('Browsing Digest extension installed');
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'PAGE_DATA') {
    savePageData(message.data)
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true; // Keep channel open for async response
  }
  
  if (message.type === 'GET_HISTORY') {
    getHistory(message.date)
      .then((data) => sendResponse({ success: true, data }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }
  
  if (message.type === 'EXPORT_DATA') {
    exportData(message.date)
      .then((data) => sendResponse({ success: true, data }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }
  
  if (message.type === 'CLEAR_HISTORY') {
    clearHistory(message.date)
      .then(() => sendResponse({ success: true }))
      .catch((error) => sendResponse({ success: false, error: error.message }));
    return true;
  }
});

// Save page data to storage
async function savePageData(pageData) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get([STORAGE_KEY], (result) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      
      let history = result[STORAGE_KEY] || [];
      
      // Add new entry
      history.push({
        ...pageData,
        id: generateId(),
        savedAt: new Date().toISOString()
      });
      
      // Trim old entries if exceeding limit
      if (history.length > MAX_ENTRIES) {
        history = history.slice(-MAX_ENTRIES);
      }
      
      chrome.storage.local.set({ [STORAGE_KEY]: history }, () => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve();
        }
      });
    });
  });
}

// Get history for a specific date (or all if no date provided)
async function getHistory(date) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get([STORAGE_KEY], (result) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      
      let history = result[STORAGE_KEY] || [];
      
      if (date) {
        // Filter by date (optimize by creating filterDate once)
        const filterDateStr = new Date(date).toDateString();
        history = history.filter((entry) => {
          return new Date(entry.timestamp).toDateString() === filterDateStr;
        });
      }
      
      resolve(history);
    });
  });
}

// Export data as JSON for the summarizer
async function exportData(date) {
  const history = await getHistory(date);
  return {
    exportedAt: new Date().toISOString(),
    date: date || 'all',
    totalPages: history.length,
    pages: history.map((entry) => ({
      url: entry.url,
      title: entry.title,
      content: entry.content,
      timestamp: entry.timestamp,
      domain: entry.domain,
      readingTime: entry.readingTime
    }))
  };
}

// Clear history for a specific date (or all if no date provided)
async function clearHistory(date) {
  return new Promise((resolve, reject) => {
    if (!date) {
      // Clear all
      chrome.storage.local.set({ [STORAGE_KEY]: [] }, () => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve();
        }
      });
    } else {
      // Clear specific date
      chrome.storage.local.get([STORAGE_KEY], (result) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        
        let history = result[STORAGE_KEY] || [];
        // Optimize by creating filterDate once
        const filterDateStr = new Date(date).toDateString();
        history = history.filter((entry) => {
          return new Date(entry.timestamp).toDateString() !== filterDateStr;
        });
        
        chrome.storage.local.set({ [STORAGE_KEY]: history }, () => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
          } else {
            resolve();
          }
        });
      });
    }
  });
}

// Generate unique ID
function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2);
}
