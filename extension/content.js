// Content script - extracts meaningful content from web pages

(function() {
  'use strict';
  
  // Avoid duplicate execution
  if (window.__browsingDigestLoaded) return;
  window.__browsingDigestLoaded = true;
  
  // Skip certain pages
  const skipPatterns = [
    /^chrome:/,
    /^chrome-extension:/,
    /^about:/,
    /^file:/,
    /^data:/,
    /^blob:/,
    /localhost/,
    /127\.0\.0\.1/,
    /\.local/
  ];
  
  // Skip if URL matches any pattern
  const currentUrl = window.location.href;
  if (skipPatterns.some(pattern => pattern.test(currentUrl))) {
    return;
  }
  
  // Wait for page to be reasonably loaded
  const captureDelay = 2000; // 2 seconds after load
  
  setTimeout(() => {
    try {
      const pageData = extractPageData();
      if (pageData && pageData.content.length > 100) {
        chrome.runtime.sendMessage({
          type: 'PAGE_DATA',
          data: pageData
        }).catch(() => {
          // Extension context may be invalidated, ignore
        });
      }
    } catch (error) {
      console.debug('Browsing Digest: Error extracting page data', error);
    }
  }, captureDelay);
  
  function extractPageData() {
    const url = window.location.href;
    const title = document.title || 'Untitled';
    const domain = window.location.hostname;
    const timestamp = new Date().toISOString();
    
    // Extract main content
    const content = extractMainContent();
    
    // Estimate reading time (average 200 words per minute)
    const wordCount = content.split(/\s+/).length;
    const readingTime = Math.ceil(wordCount / 200);
    
    return {
      url,
      title,
      domain,
      timestamp,
      content,
      wordCount,
      readingTime
    };
  }
  
  function extractMainContent() {
    // Try to find main content area using common selectors
    const mainSelectors = [
      'article',
      '[role="main"]',
      'main',
      '.post-content',
      '.article-content',
      '.entry-content',
      '.content',
      '.post',
      '#content',
      '#main'
    ];
    
    let mainElement = null;
    
    for (const selector of mainSelectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent.trim().length > 200) {
        mainElement = element;
        break;
      }
    }
    
    // Fallback to body if no main content found
    if (!mainElement) {
      mainElement = document.body;
    }
    
    // Clone to avoid modifying the actual page
    const clone = mainElement.cloneNode(true);
    
    // Remove unwanted elements
    const removeSelectors = [
      'script',
      'style',
      'noscript',
      'iframe',
      'nav',
      'header',
      'footer',
      'aside',
      '.sidebar',
      '.navigation',
      '.nav',
      '.menu',
      '.comments',
      '.comment',
      '.advertisement',
      '.ad',
      '.ads',
      '.social-share',
      '.share-buttons',
      '.related-posts',
      '.recommended',
      '[role="navigation"]',
      '[role="banner"]',
      '[role="complementary"]',
      '[aria-hidden="true"]'
    ];
    
    // Optimize: combine selectors into single query to reduce DOM lookups
    const combinedSelector = removeSelectors.join(',');
    clone.querySelectorAll(combinedSelector).forEach(el => el.remove());
    
    // Extract and clean text
    let text = clone.textContent || '';
    
    // Clean up whitespace
    text = text
      .replace(/\s+/g, ' ')           // Multiple spaces to single
      .replace(/\n\s*\n/g, '\n\n')    // Multiple newlines to double
      .trim();
    
    // Truncate if too long (max 5000 chars to save storage)
    const maxLength = 5000;
    if (text.length > maxLength) {
      text = text.substring(0, maxLength) + '... [truncated]';
    }
    
    return text;
  }
})();
