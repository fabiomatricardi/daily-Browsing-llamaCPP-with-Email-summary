// Popup script - handles UI interactions

document.addEventListener('DOMContentLoaded', () => {
  // Set date picker to today
  const datePicker = document.getElementById('datePicker');
  datePicker.value = new Date().toISOString().split('T')[0];

  // Load initial data
  refreshData();

  // Event listeners
  document.getElementById('exportBtn').addEventListener('click', exportData);
  document.getElementById('viewBtn').addEventListener('click', viewPages);
  document.getElementById('clearBtn').addEventListener('click', clearData);
  datePicker.addEventListener('change', refreshData);
});

// Consolidated data refresh function to avoid duplicate storage calls
async function refreshData() {
  const date = document.getElementById('datePicker').value;
  const container = document.getElementById('recentPages');

  try {
    // Single storage call to get all data
    const response = await chrome.runtime.sendMessage({
      type: 'GET_HISTORY',
      date: null
    });

    if (response.success) {
      const allData = response.data;

      // Filter for selected date client-side
      const filterDateStr = new Date(date).toDateString();
      const todayData = allData.filter((entry) => {
        return new Date(entry.timestamp).toDateString() === filterDateStr;
      });

      // Update stats
      document.getElementById('todayCount').textContent = todayData.length;
      document.getElementById('totalCount').textContent = allData.length;

      const totalReadingTime = todayData.reduce((sum, page) => sum + (page.readingTime || 0), 0);
      document.getElementById('readingTime').textContent = `${totalReadingTime}m`;

      // Update recent pages list
      if (todayData.length > 0) {
        // Sort by timestamp descending and take last 10
        const pages = todayData
          .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
          .slice(0, 10);

        container.innerHTML = pages.map(page => `
          <div class="page-item">
            <div class="page-icon">${getEmojiForDomain(page.domain)}</div>
            <div class="page-info">
              <div class="page-title" title="${escapeHtml(page.title)}">${escapeHtml(page.title)}</div>
              <div class="page-meta">
                <span>${page.domain}</span>
                <span>•</span>
                <span>${page.readingTime || 1}m read</span>
                <span>•</span>
                <span>${formatTime(page.timestamp)}</span>
              </div>
            </div>
          </div>
        `).join('');
      } else {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">🌐</div>
            <div>No pages for this date</div>
          </div>
        `;
      }
    }
  } catch (error) {
    console.error('Failed to load data:', error);
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <div>Error loading pages</div>
      </div>
    `;
  }
}

async function exportData() {
  const date = document.getElementById('datePicker').value;
  
  try {
    showStatus('Exporting...', 'success');
    
    const response = await chrome.runtime.sendMessage({
      type: 'EXPORT_DATA',
      date: date
    });
    
    if (response.success) {
      const data = response.data;
      
      if (data.totalPages === 0) {
        showStatus('No pages to export for this date', 'error');
        return;
      }
      
      // Create and download JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const filename = `browsing-digest-${date}.json`;
      
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      showStatus(`Exported ${data.totalPages} pages to ${filename}`, 'success');
    } else {
      showStatus('Export failed: ' + response.error, 'error');
    }
  } catch (error) {
    showStatus('Export failed: ' + error.message, 'error');
  }
}

async function viewPages() {
  const date = document.getElementById('datePicker').value;
  
  try {
    const response = await chrome.runtime.sendMessage({
      type: 'GET_HISTORY',
      date: date
    });
    
    if (response.success && response.data.length > 0) {
      // Create a simple HTML view
      const html = generateHTMLReport(response.data, date);
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      chrome.tabs.create({ url: url });
    } else {
      showStatus('No pages to view for this date', 'error');
    }
  } catch (error) {
    showStatus('Failed to view pages: ' + error.message, 'error');
  }
}

async function clearData() {
  const date = document.getElementById('datePicker').value;
  
  if (!confirm(`Clear all browsing data for ${date}?`)) {
    return;
  }
  
  try {
    const response = await chrome.runtime.sendMessage({
      type: 'CLEAR_HISTORY',
      date: date
    });
    
    if (response.success) {
      showStatus('Data cleared successfully', 'success');
      refreshData();
    } else {
      showStatus('Failed to clear data: ' + response.error, 'error');
    }
  } catch (error) {
    showStatus('Failed to clear data: ' + error.message, 'error');
  }
}

function showStatus(message, type) {
  const statusEl = document.getElementById('statusMessage');
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
  
  setTimeout(() => {
    statusEl.className = 'status';
  }, 3000);
}

function getEmojiForDomain(domain) {
  const emojiMap = {
    'github.com': '💻',
    'stackoverflow.com': '📚',
    'youtube.com': '🎬',
    'twitter.com': '🐦',
    'x.com': '🐦',
    'reddit.com': '🤖',
    'medium.com': '📝',
    'dev.to': '👨‍💻',
    'news.ycombinator.com': '🟠',
    'linkedin.com': '💼',
    'wikipedia.org': '📖',
    'google.com': '🔍',
    'amazon.com': '📦',
    'netflix.com': '🎬',
    'spotify.com': '🎵'
  };
  
  for (const [key, emoji] of Object.entries(emojiMap)) {
    if (domain.includes(key)) {
      return emoji;
    }
  }
  
  return '🌐';
}

function formatTime(timestamp) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function generateHTMLReport(pages, date) {
  const sortedPages = pages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  // Calculate total reading time once
  const totalReadingTime = pages.reduce((sum, p) => sum + (p.readingTime || 0), 0);

  return `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Browsing Digest - ${date}</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 800px;
      margin: 0 auto;
      padding: 40px 20px;
      background: #f5f5f5;
      color: #333;
    }
    h1 {
      color: #667eea;
      border-bottom: 2px solid #667eea;
      padding-bottom: 10px;
    }
    .page {
      background: white;
      padding: 20px;
      margin: 20px 0;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .page-title {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 10px;
    }
    .page-title a {
      color: #667eea;
      text-decoration: none;
    }
    .page-title a:hover {
      text-decoration: underline;
    }
    .page-meta {
      font-size: 12px;
      color: #888;
      margin-bottom: 15px;
    }
    .page-content {
      font-size: 14px;
      line-height: 1.6;
      color: #555;
      max-height: 200px;
      overflow: hidden;
      position: relative;
    }
    .page-content::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 50px;
      background: linear-gradient(transparent, white);
    }
  </style>
</head>
<body>
  <h1>📚 Browsing Digest - ${date}</h1>
  <p>Total pages: ${pages.length} | Total reading time: ${totalReadingTime} minutes</p>
  
  ${sortedPages.map(page => `
    <div class="page">
      <div class="page-title">
        <a href="${escapeHtml(page.url)}" target="_blank">${escapeHtml(page.title)}</a>
      </div>
      <div class="page-meta">
        ${page.domain} • ${formatTime(page.timestamp)} • ${page.readingTime || 1} min read • ${page.wordCount || 0} words
      </div>
      <div class="page-content">${escapeHtml(page.content).substring(0, 500)}...</div>
    </div>
  `).join('')}
</body>
</html>
  `;
}
