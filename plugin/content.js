// Content script for Video Download Assistant

class VideoInfoExtractor {
  constructor() {
    this.videoInfo = null;
    this.init();
  }

  init() {
    // Extract video information on page load
    this.extractVideoInfo();
    
    // Re-extract if URL changes (for SPAs)
    let currentUrl = window.location.href;
    const observer = new MutationObserver(() => {
      if (window.location.href !== currentUrl) {
        currentUrl = window.location.href;
        setTimeout(() => this.extractVideoInfo(), 1000);
      }
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  extractVideoInfo() {
    const url = window.location.href;
    let title = '';
    let thumbnail = '';
    let episodeLinks = [];

    // Special handling for ogladajanime.pl
    if (url.includes('ogladajanime.pl')) {
      // Try to extract title from ogladajanime.pl specific selectors
      const ogladajTitle = document.querySelector('h1.entry-title');
      if (ogladajTitle) {
        title = ogladajTitle.textContent?.trim() || '';
      }

      // Try to extract thumbnail from ogladajanime.pl specific selectors
      const ogladajThumbnail = document.querySelector('.post-thumbnail img');
      if (ogladajThumbnail) {
        thumbnail = ogladajThumbnail.src || '';
      }

      // If still no thumbnail, try the video element
      if (!thumbnail) {
        const videoElement = document.querySelector('video');
        if (videoElement) {
          thumbnail = videoElement.poster || '';
        }
      }

      // Extract episode links from different authors
      episodeLinks = this.extractEpisodeLinks();
    }

    // If not ogladajanime.pl or if we didn't find info, use generic selectors
    if (!title || !url.includes('ogladajanime.pl')) {
      // Try to extract title from various sources
      const titleSelectors = [
        'title',
        'h1',
        '[data-title]',
        '.video-title',
        '.title',
        'meta[property="og:title"]',
        'meta[name="title"]'
      ];

      for (const selector of titleSelectors) {
        const element = document.querySelector(selector);
        if (element) {
          if (element.tagName === 'META') {
            title = element.content;
          } else {
            title = element.textContent || element.innerText;
          }
          if (title && title.trim()) {
            title = title.trim();
            break;
          }
        }
      }
    }

    // If not ogladajanime.pl or if we didn't find thumbnail, use generic selectors
    if (!thumbnail || !url.includes('ogladajanime.pl')) {
      // Try to extract thumbnail
      const thumbnailSelectors = [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        'video',
        '.video-thumbnail img',
        '.thumbnail img'
      ];

      for (const selector of thumbnailSelectors) {
        const element = document.querySelector(selector);
        if (element) {
          if (element.tagName === 'META') {
            thumbnail = element.content;
          } else if (element.tagName === 'VIDEO') {
            thumbnail = element.poster || '';
          } else {
            thumbnail = element.src || '';
          }
          if (thumbnail) break;
        }
      }
    }

    // Clean title
    if (title) {
      title = title.replace(/^\s*-\s*/, '').replace(/\s*-\s*$/, '');
      title = title.replace(/\s+/g, ' ').trim();
      if (title.length > 100) {
        title = title.substring(0, 100) + '...';
      }
    }

    this.videoInfo = {
      url: url,
      title: title || 'Unknown Title',
      thumbnail: thumbnail,
      timestamp: Date.now(),
      domain: this.getDomainFromUrl(url),
      episodeLinks: episodeLinks
    };

    // Send to background script
    chrome.runtime.sendMessage({
      action: 'getVideoInfo',
      data: this.videoInfo
    });
  }

  getDomainFromUrl(url) {
    try {
      const domain = new URL(url).hostname;
      // Remove www. prefix if present
      return domain.replace(/^www\./, '');
    } catch (e) {
      return 'unknown';
    }
  }

  extractEpisodeLinks() {
    const links = [];

    console.log('Extracting episode links for ogladajanime.pl');

    // Try to find episode link containers - expanded selectors for ogladajanime.pl
    const linkContainers = document.querySelectorAll(
      '.episode-links .link-container, ' +
      '.mirror-links .mirror-link, ' +
      '.mirror-container .mirror-item, ' +
      '.download-links .link-item, ' +
      '.episode-mirrors .mirror, ' +
      '.link-list .link-entry'
    );

    console.log('Found link containers:', linkContainers.length);

    linkContainers.forEach(container => {
      // Extract author name - expanded selectors
      const authorElement = container.querySelector(
        '.author-name, .mirror-author, .link-author, ' +
        '.mirror-title, .link-title, .source-name'
      );
      const author = authorElement ? authorElement.textContent?.trim() : 'Unknown Author';

      // Extract link URL - expanded selectors
      const linkElement = container.querySelector(
        'a[href], .download-link, .mirror-url, .link-url'
      );
      let url = '';
      if (linkElement) {
        url = linkElement.href || '';
      }

      // Extract link text/description - expanded selectors
      const descElement = container.querySelector(
        '.link-desc, .mirror-desc, .link-description, ' +
        '.mirror-description, .source-desc'
      );
      const description = descElement ? descElement.textContent?.trim() : '';

      // If no description, try to get it from link text or container
      if (!description && linkElement) {
        const linkText = linkElement.textContent?.trim() || '';
        if (linkText && linkText !== url) {
          description = linkText;
        }
      }

      if (url) {
        links.push({
          author: author,
          url: url,
          description: description || 'Link do odcinka'
        });
      }
    });

    console.log('Links from containers:', links.length);

    // Alternative approach: look for specific link patterns - expanded domains
    if (links.length === 0) {
      const allLinks = document.querySelectorAll(
        'a[href*="ogladajanime.pl"], ' +
        'a[href*="streamtape.com"], ' +
        'a[href*="mp4upload.com"], ' +
        'a[href*="yourupload.com"], ' +
        'a[href*="streamlare.com"], ' +
        'a[href*="mixdrop.co"], ' +
        'a[href*="dood.to"], ' +
        'a[href*="filemoon.sx"], ' +
        'a[href*="voe.sx"], ' +
        'a[href*="vidstreaming.io"]'
      );

      console.log('Found all links:', allLinks.length);

      allLinks.forEach(link => {
        const url = link.href;
        const text = link.textContent?.trim() || '';
        const parent = link.closest('.link-item, .mirror-item, li, .mirror, .source');
        const author = parent ? parent.textContent?.replace(url, '')?.replace(text, '')?.trim() : 'Unknown';

        links.push({
          author: author || 'Unknown Author',
          url: url,
          description: text || 'Link do odcinka'
        });
      });
    }

    // Remove duplicates
    const uniqueLinks = [];
    const seenUrls = new Set();
    links.forEach(link => {
      if (!seenUrls.has(link.url)) {
        seenUrls.add(link.url);
        uniqueLinks.push(link);
      }
    });

    console.log('Final unique links:', uniqueLinks.length);
    console.log('Links:', uniqueLinks);

    return uniqueLinks;
  }

  getVideoInfo() {
    return this.videoInfo;
  }
}

// Initialize video info extractor
const videoExtractor = new VideoInfoExtractor();

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getPageVideoInfo') {
    sendResponse(videoExtractor.getVideoInfo());
  }
});
