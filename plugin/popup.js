import { updateUI } from './ui.js';
import { loadSettings, saveSettings } from './settings.js';
import { downloadVideo } from './download.js';
import { loadQueue } from './queue.js';

class VideoDownloadAssistant {
    constructor() {
        this.currentView = 'main-view';
        this.serverPort = 8080;
        this.serverIp = '127.0.0.1';
        this.downloadFolder = 'Downloads';
        this.videoInfo = null;
        this.translations = {};
        this.currentLanguage = 'en';

        this.init();
    }

    async init() {
        await loadSettings(this);
        await this.loadTranslations();
        this.setupEventListeners();
        this.checkServerStatus();
        this.getVideoInfo();
        updateUI(this);

        // Check server status periodically
        setInterval(() => this.checkServerStatus(), 5000);
    }

    async loadTranslations() {
        try {
            const res = await fetch(`/_locales/${this.currentLanguage}/messages.json`);
            this.translations = await res.json();
        } catch (e) {
            console.error('Failed to load translations:', e);
            try {
                const res = await fetch('/_locales/en/messages.json');
                this.translations = await res.json();
            } catch {
                this.translations = {};
            }
        }
    }

    t(key) {
        return this.translations[key]?.message || key;
    }

    getTranslationKey(elementId) {
        const map = {
            'app-title': 'extensionName',
            'server-status-label': 'serverStatus',
            'video-title-label': 'videoTitle',
            'quality-label': 'quality',
            'download-btn-text': 'downloadVideo',
            'settings-title': 'settings',
            'language-label': 'language',
            'server-port-label': 'serverPort',
            'download-folder-label': 'downloadFolder',
            'ytdlp-status-label': 'ytDlpStatus',
            'save-settings-btn': 'save',
            'cancel-settings-btn': 'cancel',
            'status-text': 'checking',
            'ytdlp-status-text': 'checking'
        };
        return map[elementId];
    }

    updateSettingsFields() {
        const languageSelect = document.getElementById('language-select');
        const serverPortInput = document.getElementById('server-port-input');
        const serverIpInput = document.getElementById('serveripinput');
        const downloadFolderInput = document.getElementById('download-folder-input');

        if (languageSelect) languageSelect.value = this.currentLanguage;
        if (serverPortInput) serverPortInput.value = this.serverPort;
        if (serverIpInput) serverIpInput.value = this.serverIp;
        if (downloadFolderInput) downloadFolderInput.value = this.downloadFolder;
    }

    setupEventListeners() {
        document.getElementById('settings-btn')?.addEventListener('click', () => this.showView('settings-view'));
        document.getElementById('back-btn')?.addEventListener('click', () => this.showView('main-view'));
        document.getElementById('download-btn')?.addEventListener('click', () => downloadVideo(this));
        document.getElementById('show-links-btn')?.addEventListener('click', () => this.showEpisodeLinks());
        document.getElementById('save-settings-btn')?.addEventListener('click', async () => {
            await saveSettings(this);
        });
        document.getElementById('cancel-settings-btn')?.addEventListener('click', () => this.showView('main-view'));

        document.getElementById('language-select')?.addEventListener('change', async e => {
            const newLang = e.target.value;
            if (newLang !== this.currentLanguage) {
                this.currentLanguage = newLang;
                await this.loadTranslations();
                updateUI(this);
            }
        });

        document.getElementById('format-select')?.addEventListener('change', e => {
            if (e.target.value === 'mp3') document.getElementById('quality-select').value = 'bestaudio';
        });

        document.getElementById('quality-select')?.addEventListener('change', e => {
            const formatSelect = document.getElementById('format-select');
            if (e.target.value === 'bestaudio' && formatSelect.value !== 'mp3') formatSelect.value = 'mp3';
        });

        // Queue view buttons
        const queueBtn = document.getElementById("queue-btn");
        const queueBackBtn = document.getElementById("queue-back-btn");

        queueBtn?.addEventListener('click', () => {
            this.showView('queue-view');
            loadQueue(this);
        });
        queueBackBtn?.addEventListener('click', () => this.showView('main-view'));
    }

    showView(viewId) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(viewId)?.classList.add('active');
        this.currentView = viewId;

        if (viewId === 'settings-view') this.checkYtDlpStatus();
    }

    async checkServerStatus() {
        const statusElement = document.getElementById('server-status');
        const statusTextElement = document.getElementById('status-text');
        try {
            const res = await fetch(`http://${this.serverIp}:${this.serverPort}/status`);
            if (res.ok) {
                const serverInfo = await res.json();
                console.log('Server status response:', serverInfo); // Debug log
                statusElement.className = 'status-indicator connected';
                statusTextElement.textContent = this.getServerInfoText(serverInfo);
            } else throw new Error('Server not responding');
        } catch (error) {
            console.error('Server status error:', error);
            statusElement.className = 'status-indicator disconnected';
            statusTextElement.textContent = this.t('disconnected') || 'Disconnected';
        }
    }

    getServerInfoText(serverInfo) {
        if (!serverInfo || Object.keys(serverInfo).length === 0) {
            return this.t('connected') || 'Connected';
        }

        // Display server information based on actual server response
        let infoText = this.t('connected') || 'Connected';

        if (serverInfo.version) {
            // Remove 'v' prefix if already present to avoid double 'v'
            const version = serverInfo.version.startsWith('v')
                ? serverInfo.version.substring(1)
                : serverInfo.version;
            infoText += ` | v${version}`;
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
        const statusElement = document.getElementById('ytdlp-status');
        const statusTextElement = document.getElementById('ytdlp-status-text');

        statusElement.className = 'status-indicator checking';
        statusTextElement.textContent = this.t('checking') || 'Checking...';

        try {
            const res = await fetch(`http://${this.serverIp}:${this.serverPort}/check-ytdlp`);
            const data = await res.json();
            if (data.installed) {
                statusElement.className = 'status-indicator connected';
                statusTextElement.textContent = this.t('ytDlpInstalled') || 'yt-dlp installed';
            } else {
                statusElement.className = 'status-indicator disconnected';
                statusTextElement.textContent = this.t('ytDlpNotInstalled') || 'yt-dlp not installed';
            }
        } catch {
            statusElement.className = 'status-indicator disconnected';
            statusTextElement.textContent = this.t('serverNotRunning') || 'Server not running';
        }
    }

    async getVideoInfo() {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            const response = await chrome.tabs.sendMessage(tab.id, { action: 'getPageVideoInfo' });
            this.videoInfo = response || {
                url: tab.url,
                title: tab.title || 'Unknown',
                thumbnail: '',
                timestamp: Date.now(),
                domain: this.getDomainFromUrl(tab.url),
                episodeLinks: []
            };
            this.displayVideoInfo();

            // Don't automatically show episode links popup - user will click the button
        } catch {
            console.error('Failed to get video info');
        }
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

    displayVideoInfo() {
        if (!this.videoInfo) return;

        const titleEl = document.getElementById('video-title');
        const urlEl = document.getElementById('current-url');
        const thumbEl = document.getElementById('video-thumbnail');
        const placeholderEl = document.getElementById('thumbnail-placeholder');

        titleEl.textContent = this.videoInfo.title;
        urlEl.textContent = new URL(this.videoInfo.url).hostname;

        if (this.videoInfo.thumbnail) {
            thumbEl.src = this.videoInfo.thumbnail;
            thumbEl.style.display = 'block';
            placeholderEl.style.display = 'none';
        } else {
            thumbEl.src = '';
            thumbEl.style.display = 'none';
            placeholderEl.style.display = 'flex';
        }

        // Hide download button for ogladajanime.pl
        this.updateDownloadButtonVisibility();
    }

    updateDownloadButtonVisibility() {
        const downloadBtn = document.getElementById('download-btn');
        const showLinksBtn = document.getElementById('show-links-btn');
        if (downloadBtn) {
            console.log('Video info:', this.videoInfo); // Debug log
            if (this.videoInfo?.domain) {
                console.log('Domain:', this.videoInfo.domain); // Debug log
                // Hide download button for ogladajanime.pl
                if (this.videoInfo.domain.includes('ogladajanime.pl')) {
                    console.log('Hiding download button for ogladajanime.pl'); // Debug log
                    downloadBtn.style.display = 'none';
                    // Show show links button if there are episode links
                    if (this.videoInfo.episodeLinks && this.videoInfo.episodeLinks.length > 0) {
                        showLinksBtn.style.display = 'block';
                    } else {
                        showLinksBtn.style.display = 'none';
                    }
                } else {
                    console.log('Showing download button for domain:', this.videoInfo.domain); // Debug log
                    downloadBtn.style.display = 'block';
                    showLinksBtn.style.display = 'none';
                }
            } else {
                console.log('No domain information in video info'); // Debug log
                downloadBtn.style.display = 'block';
                showLinksBtn.style.display = 'none';
            }
        }
    }

    isYouTubeDomain(url) {
        try {
            const host = new URL(url).hostname.toLowerCase();
            const youtubeDomains = ['youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','youtube-nocookie.com'];
            return youtubeDomains.some(d => host === d || host.endsWith('.' + d));
        } catch { return false; }
    }

    getDefaultQualityText(value) {
        const defaults = {
            'best': 'Best Quality (1440p/1080p)',
            'best[height<=720]': 'HD 720p or lower',
            'best[height<=480]': 'SD 480p or lower',
            'worst': 'Lowest Quality',
            'bestaudio': 'Audio Only (High Quality)'
        };
        return defaults[value] || value;
    }

    showEpisodeLinksPopup() {
        console.log('Showing episode links popup for:', this.videoInfo.episodeLinks);

        // Create a popup window with episode links
        chrome.windows.create({
            url: `dialog.html?episodeLinks=${encodeURIComponent(JSON.stringify(this.videoInfo.episodeLinks))}&title=${encodeURIComponent(this.videoInfo.title)}`,
            type: 'popup',
            width: 600,
            height: 400
        });
    }

    showEpisodeLinks() {
        console.log('Showing episode links in popup:', this.videoInfo.episodeLinks);

        if (!this.videoInfo?.episodeLinks || this.videoInfo.episodeLinks.length === 0) {
            console.log('No episode links available');
            return;
        }

        const linksSection = document.getElementById('episode-links-section');
        const linksContainer = document.getElementById('episode-links-container');

        // Clear previous links
        linksContainer.innerHTML = '';

        // Add each episode link
        this.videoInfo.episodeLinks.forEach((link, index) => {
            const linkElement = document.createElement('div');
            linkElement.className = 'episode-link-item';

            const authorElement = document.createElement('div');
            authorElement.className = 'episode-link-author';
            authorElement.textContent = `${index + 1}. ${link.author || 'Unknown Author'}`;

            const descElement = document.createElement('div');
            descElement.className = 'episode-link-desc';
            descElement.textContent = link.description || link.url;

            const buttonElement = document.createElement('button');
            buttonElement.className = 'episode-link-button';
            buttonElement.textContent = 'Użyj tego źródła';
            buttonElement.addEventListener('click', () => {
                this.useEpisodeLink(link);
            });

            linkElement.appendChild(authorElement);
            linkElement.appendChild(descElement);
            linkElement.appendChild(buttonElement);
            linksContainer.appendChild(linkElement);
        });

        // Show the links section
        linksSection.style.display = 'block';
    }

    useEpisodeLink(link) {
        console.log('Using episode link:', link);

        // For now, just open the link in a new tab
        // In future, this could be integrated with the download functionality
        chrome.tabs.create({ url: link.url });
    }
}

// Initialize the app
document.addEventListener('DOMContentLoaded', () => new VideoDownloadAssistant());
