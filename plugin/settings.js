export async function loadSettings(vda) {
    const settings = await chrome.storage.sync.get([
        'language', 'serverPort', 'serveripinput', 'downloadFolder'
    ]);

    vda.currentLanguage = settings.language || 'en';
    vda.serverPort = settings.serverPort || 8080;
    vda.serverIp = settings.serveripinput || '127.0.0.1';
    vda.downloadFolder = settings.downloadFolder || 'Downloads';

    vda.updateSettingsFields();
}

export async function saveSettings(vda) {
    try {
        const language = document.getElementById('language-select').value;
        const serverPort = parseInt(document.getElementById('server-port-input').value);
        const serverIp = document.getElementById('serveripinput').value.trim();
        const downloadFolder = document.getElementById('download-folder-input').value;

        if (!serverIp) { alert('Please enter a valid server IP'); return; }
        if (serverPort < 1 || serverPort > 65535) { alert('Please enter a valid port (1-65535)'); return; }

        await chrome.storage.sync.set({ language, serveripinput: serverIp, serverPort, downloadFolder });

        const oldLang = vda.currentLanguage;
        vda.currentLanguage = language;
        vda.serverPort = serverPort;
        vda.serverIp = serverIp;
        vda.downloadFolder = downloadFolder;

        if (language !== oldLang) await vda.loadTranslations();

        updateUI(vda);
        vda.checkServerStatus();
    } finally {
        // Always return to main view, even if there are errors
        vda.showView('main-view');
    }
}
