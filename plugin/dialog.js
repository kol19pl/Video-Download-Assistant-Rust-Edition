// Dialog script for Video Download Assistant

class VideoDownloadAssistant {
  constructor() {
    this.currentVideoInfo = null;
    this.settings = {
      language: 'en',
      serverPort: 8080,
      downloadFolder: 'Downloads'
    };
    this.translations = {};

    this.init();
  }

  async init() {
    // Load settings and translations
    await this.loadSettings();
    await this.loadTranslations();

    // Initialize UI
    this.initializeElements();
    this.attachEventListeners();

    // Start checking server status
    this.checkServerStatus();
    setInterval(() => this.checkServerStatus(), 5000);

    // Load video info
    this.loadVideoInfo();

    // Listen for video info updates from background
    chrome.runtime.onMessage.addListener((request) => {
      if (request.action === 'videoInfoReceived') {
        this.updateVideoInfo(request.data);
      }
    });

    // Poll for video info updates every 2 seconds
    setInterval(() => this.loadVideoInfo(), 2000);
  }

  initializeElements() {
    // Main view elements
    this.videoCard = document.getElementById('video-card');
    this.cardThumbnail = document.getElementById('card-thumbnail');
    this.cardThumbnailPlaceholder = document.getElementById('card-thumbnail-placeholder');
    this.siteFavicon = document.getElementById('site-favicon');
    this.cardTitle = document.getElementById('card-title');
    this.serverStatus = document.getElementById('server-status');
    this.statusText = document.getElementById('status-text');

    // Settings elements
    this.settingsBtn = document.getElementById('settings-btn');
    this.settingsView = document.getElementById('settings-view');
    this.mainView = document.getElementById('main-view');
    this.backBtn = document.getElementById('back-btn');
    this.languageSelect = document.getElementById('language-select');
    this.serverPortInput = document.getElementById('server-port-input');
    this.downloadFolderInput = document.getElementById('download-folder-input');
    this.saveSettingsBtn = document.getElementById('save-settings-btn');
    this.cancelSettingsBtn = document.getElementById('cancel-settings-btn');
    this.ytdlpStatus = document.getElementById('ytdlp-status');
    this.ytdlpStatusText = document.getElementById('ytdlp-status-text');
  }

  attachEventListeners() {
    // Video card click - open new window
    this.videoCard.addEventListener('click', () => this.openDownloadWindow());

    // Settings navigation
    this.settingsBtn.addEventListener('click', () => this.openSettings());
    this.backBtn.addEventListener('click', () => this.closeSettings());
    this.cancelSettingsBtn.addEventListener('click', () => this.closeSettings());
    this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());

    // Language change
    this.languageSelect.addEventListener('change', (e) => {
      this.settings.language = e.target.value;
      this.loadTranslations();
    });
  }

  async loadSettings() {
    const stored = await chrome.storage.sync.get(['language', 'serverPort', 'serveripinput', 'downloadFolder']);
    this.settings = {
      language: stored.language || 'en',
      serverIp: stored.serveripinput || '127.0.0.1',
      serverPort: stored.serverPort || 8080,
      downloadFolder: stored.downloadFolder || 'Downloads'
    };

    // Update UI
    if (this.languageSelect) {
      this.languageSelect.value = this.settings.language;
    }
    if (this.serverPortInput) {
      this.serverPortInput.value = this.settings.serverPort;
    }
    if (this.downloadFolderInput) {
      this.downloadFolderInput.value = this.settings.downloadFolder;
    }
  }

  async loadTranslations() {
    try {
      const response = await fetch(`/_locales/${this.settings.language}/messages.json`);
      const messages = await response.json();

      this.translations = {};
      for (const [key, value] of Object.entries(messages)) {
        this.translations[key] = value.message;
      }

      this.updateUIText();
    } catch (error) {
      console.error('Failed to load translations:', error);
    }
  }

  updateUIText() {
    // Main view
    document.getElementById('app-title').textContent = this.translations.extensionName || 'Video Download Assistant';
    document.getElementById('server-status-label').textContent = this.translations.serverStatus || 'Server Status:';

    // Settings
    document.getElementById('settings-title').textContent = this.translations.settings || 'Settings';
    document.getElementById('language-label').textContent = this.translations.language || 'Language:';
    document.getElementById('server-port-label').textContent = this.translations.serverPort || 'Server Port:';
    document.getElementById('download-folder-label').textContent = this.translations.downloadFolder || 'Download Folder:';
    document.getElementById('ytdlp-status-label').textContent = this.translations.ytDlpStatus || 'yt-dlp Status:';
    document.getElementById('save-settings-btn').textContent = this.translations.save || 'Save';
    document.getElementById('cancel-settings-btn').textContent = this.translations.cancel || 'Cancel';
  }

  async loadVideoInfo() {
    try {
      // Get video info from background script
      const response = await chrome.runtime.sendMessage({ action: 'getLatestVideoInfo' });

      if (response) {
        this.updateVideoInfo(response);
      } else {
        // Try to get from active tab
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab) {
          chrome.tabs.sendMessage(tab.id, { action: 'getPageVideoInfo' }, (info) => {
            if (info) {
              this.updateVideoInfo(info);
            }
          });
        }
      }
    } catch (error) {
      console.error('Failed to load video info:', error);
    }
  }

  updateVideoInfo(info) {
    if (!info) return;

    this.currentVideoInfo = info;

    // Update card
    this.cardTitle.textContent = info.title || 'Unknown Title';

    if (info.thumbnail) {
      this.cardThumbnail.src = info.thumbnail;
      this.cardThumbnail.style.display = 'block';
      this.cardThumbnailPlaceholder.style.display = 'none';
    } else {
      this.cardThumbnail.style.display = 'none';
      this.cardThumbnailPlaceholder.style.display = 'flex';
    }

    // Get favicon from URL
    if (info.url) {
      try {
        const url = new URL(info.url);
        const faviconUrl = `${url.protocol}//${url.hostname}/favicon.ico`;
        this.siteFavicon.src = faviconUrl;
        this.siteFavicon.style.display = 'block';

        this.siteFavicon.onerror = () => {
          this.siteFavicon.style.display = 'none';
        };
      } catch (e) {
        this.siteFavicon.style.display = 'none';
      }
    }
  }

  openDownloadWindow() {
    if (!this.currentVideoInfo) return;

    // Encode video info to pass as URL parameter
    const videoInfoEncoded = encodeURIComponent(JSON.stringify(this.currentVideoInfo));

    // Open new popup window with dialog
    chrome.windows.create({
      url: `dialog.html?videoInfo=${videoInfoEncoded}`,
      type: 'popup',
      width: 450,
      height: 600
    });
  }

  async checkServerStatus() {
    try {
      const response = await fetch(`http://${this.settings.serverIp}:${this.settings.serverPort}/status`);

      if (response.ok) {
        const serverInfo = await response.json();
        this.serverStatus.className = 'status-indicator connected';
        this.statusText.textContent = this.getServerInfoText(serverInfo);

        // Check yt-dlp status if in settings
        if (this.ytdlpStatus) {
          this.checkYtDlpStatus();
        }
      } else {
        throw new Error('Server not responding');
      }
    } catch (error) {
      this.serverStatus.className = 'status-indicator disconnected';
      this.statusText.textContent = this.translations.disconnected || 'Disconnected';

      if (this.ytdlpStatus) {
        this.ytdlpStatus.className = 'status-indicator disconnected';
        this.ytdlpStatusText.textContent = this.translations.serverNotRunning || 'Server not running';
      }
    }
  }

  getServerInfoText(serverInfo) {
    if (!serverInfo || Object.keys(serverInfo).length === 0) {
      return this.translations.connected || 'Connected';
    }

    // Display server information based on actual server response
    let infoText = this.translations.connected || 'Connected';

    if (serverInfo.version) {
      infoText += ` | v${serverInfo.version}`;
    }

    if (serverInfo.downloads_folder) {
      // Show folder name (extract just the folder name from path)
      const folderPath = serverInfo.downloads_folder;
      const folderName = folderPath.split(/[\\/]/).pop() || 'Downloads';
      infoText += ` | ${folderName}`;
    }

    return infoText;
  }

  async checkYtDlpStatus() {
    try {
      const response = await fetch(`http://${this.settings.serverIp}:${this.settings.serverPort}/ytdlp-status`);

      if (response.ok) {
        const data = await response.json();

        if (data.installed) {
          this.ytdlpStatus.className = 'status-indicator connected';
          this.ytdlpStatusText.textContent = this.translations.ytDlpInstalled || 'yt-dlp is installed';
        } else {
          this.ytdlpStatus.className = 'status-indicator disconnected';
          this.ytdlpStatusText.textContent = this.translations.ytDlpNotInstalled || 'yt-dlp is not installed';
        }
      }
    } catch (error) {
      this.ytdlpStatus.className = 'status-indicator disconnected';
      this.ytdlpStatusText.textContent = this.translations.checkingYtDlp || 'Checking...';
    }
  }

  openSettings() {
    this.mainView.classList.remove('active');
    this.settingsView.classList.add('active');
    this.checkYtDlpStatus();
  }

  closeSettings() {
    this.settingsView.classList.remove('active');
    this.mainView.classList.add('active');
  }

  async saveSettings() {
    this.settings.language = this.languageSelect.value;
    this.settings.serverPort = parseInt(this.serverPortInput.value) || 8080;
    this.settings.downloadFolder = this.downloadFolderInput.value || 'Downloads';

    await chrome.storage.sync.set(this.settings);

    // Reload translations if language changed
    await this.loadTranslations();

    this.closeSettings();
  }
}

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
  new VideoDownloadAssistant();
});

class DownloadDialog {
  constructor() {
    this.videoInfo = null;
    this.settings = null;
    this.translations = {};
    this.init();
  }

  async init() {
    // Get video info from URL params
    const params = new URLSearchParams(window.location.search);
    const videoInfoJson = params.get('videoInfo');
    
    if (videoInfoJson) {
      this.videoInfo = JSON.parse(decodeURIComponent(videoInfoJson));
    }
    
    // Load settings and translations
    await this.loadSettings();
    await this.loadTranslations();
    
    // Initialize UI
    this.initializeElements();
    this.attachEventListeners();
    this.updateVideoInfo();
  }

  initializeElements() {
    this.dialogThumbnail = document.getElementById('dialog-thumbnail');
    this.dialogThumbnailPlaceholder = document.getElementById('dialog-thumbnail-placeholder');
    this.dialogTitle = document.getElementById('dialog-title');
    this.downloadTypeRadios = document.querySelectorAll('input[name="downloadType"]');
    this.videoQualityGroup = document.getElementById('video-quality-group');
    this.videoQualitySelect = document.getElementById('video-quality-select');
    this.audioQualitySelect = document.getElementById('audio-quality-select');
    this.audioFormatSelect = document.getElementById('audio-format-select');
    this.dialogDownloadBtn = document.getElementById('dialog-download-btn');
    this.dialogDownloadText = document.getElementById('dialog-download-text');
    this.dialogSpinner = document.getElementById('dialog-spinner');
    this.dialogStatus = document.getElementById('dialog-status');
    this.dialogStatusText = document.getElementById('dialog-status-text');
  }

  attachEventListeners() {
    // Download type change
    this.downloadTypeRadios.forEach(radio => {
      radio.addEventListener('change', (e) => this.onDownloadTypeChange(e.target.value));
    });
    
    // Download button
    this.dialogDownloadBtn.addEventListener('click', () => this.startDownload());
  }

  async loadSettings() {
    const stored = await chrome.storage.sync.get(['language', 'serverPort', 'serveripinput', 'downloadFolder']);
    this.settings = {
      language: stored.language || 'en',
      serverIp: stored.serveripinput || '127.0.0.1',
      serverPort: stored.serverPort || 8080,
      downloadFolder: stored.downloadFolder || 'Downloads'
    };
  }

  async loadTranslations() {
    try {
      const response = await fetch(`/_locales/${this.settings.language}/messages.json`);
      const messages = await response.json();
      
      this.translations = {};
      for (const [key, value] of Object.entries(messages)) {
        this.translations[key] = value.message;
      }
      
      this.updateUIText();
    } catch (error) {
      console.error('Failed to load translations:', error);
    }
  }

  updateUIText() {
    document.getElementById('download-type-label').textContent = this.translations.downloadType || 'Download Type:';
    document.getElementById('download-video-label').textContent = this.translations.downloadVideo || 'Video';
    document.getElementById('download-audio-label').textContent = this.translations.downloadAudioOnly || 'Audio Only';
    document.getElementById('video-quality-label').textContent = this.translations.videoQuality || 'Video Quality:';
    document.getElementById('audio-quality-label').textContent = this.translations.audioQuality || 'Audio Quality:';
    document.getElementById('audio-format-label').textContent = this.translations.audioFormat || 'Audio Format:';
    this.dialogDownloadText.textContent = this.translations.download || 'Download';
    
    // Update quality options
    const qualityOptions = this.videoQualitySelect.options;
    qualityOptions[0].textContent = this.translations.bestQuality || 'Best Quality (1440p/1080p)';
    qualityOptions[1].textContent = this.translations.quality1080p || '1080p or lower';
    qualityOptions[2].textContent = this.translations.hd720Quality || '720p or lower';
    qualityOptions[3].textContent = this.translations.sd480Quality || '480p or lower';
    qualityOptions[4].textContent = this.translations.lowestQuality || 'Lowest Quality';
  }

  updateVideoInfo() {
    if (!this.videoInfo) return;
    
    this.dialogTitle.textContent = this.videoInfo.title || 'Unknown Title';
    
    if (this.videoInfo.thumbnail) {
      this.dialogThumbnail.src = this.videoInfo.thumbnail;
      this.dialogThumbnail.style.display = 'block';
      this.dialogThumbnailPlaceholder.style.display = 'none';
    } else {
      this.dialogThumbnail.style.display = 'none';
      this.dialogThumbnailPlaceholder.style.display = 'flex';
    }
  }

  onDownloadTypeChange(type) {
    if (type === 'video') {
      this.videoQualityGroup.style.display = 'block';
    } else {
      this.videoQualityGroup.style.display = 'none';
    }
  }

  async startDownload() {
    if (!this.videoInfo) return;
    
    // Disable button
    this.dialogDownloadBtn.disabled = true;
    this.dialogDownloadText.style.display = 'none';
    this.dialogSpinner.style.display = 'block';
    this.dialogStatus.style.display = 'none';
    
    try {
      // Get download options
      const downloadType = document.querySelector('input[name="downloadType"]:checked').value;
      const videoQuality = this.videoQualitySelect.value;
      const audioQuality = this.audioQualitySelect.value;
      const audioFormat = this.audioFormatSelect.value;
      
      // Prepare download data
      const downloadData = {
        url: this.videoInfo.url,
        title: this.videoInfo.title,
        downloadType: downloadType,
        videoQuality: videoQuality,
        audioQuality: audioQuality,
        audioFormat: audioFormat,
        folder: this.settings.downloadFolder
      };
      
      // Send to server
      const response = await fetch(`http://${this.settings.serverIp}:${this.settings.serverPort}/download`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(downloadData)
      });
      
      if (response.ok) {
        const result = await response.json();
        this.showStatus(this.translations.downloadComplete || 'Download started! Check your downloads folder.', 'success');
        
        // Close window after 2 seconds
        setTimeout(() => {
          window.close();
        }, 2000);
      } else {
        throw new Error('Server error');
      }
    } catch (error) {
      console.error('Download failed:', error);
      this.showStatus(this.translations.downloadFailed || 'Download failed. Please check server connection.', 'error');
    } finally {
      // Re-enable button
      this.dialogDownloadBtn.disabled = false;
      this.dialogDownloadText.style.display = 'inline';
      this.dialogSpinner.style.display = 'none';
    }
  }

  showStatus(message, type) {
    this.dialogStatusText.textContent = message;
    this.dialogStatus.className = 'dialog-status ' + type;
    this.dialogStatus.style.display = 'block';
  }
}

// Initialize the dialog
document.addEventListener('DOMContentLoaded', () => {
  new DownloadDialog();
});
