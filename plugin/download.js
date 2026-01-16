import { showStatus } from './ui.js';

export async function isUrlInQueue(vda, url) {
    try {
        const res = await fetch(`http://${vda.serverIp}:${vda.serverPort}/queue`);
        const queue = await res.json();
        return queue.some(item => item.url === url);
    } catch (e) {
        console.error('Failed to fetch queue:', e);
        return false;
    }
}

export async function downloadVideo(vda) {
    if (!vda.videoInfo) {
        showStatus(vda, vda.t('unknownError') || 'Unknown error', 'error');
        return;
    }

    const alreadyInQueue = await isUrlInQueue(vda, vda.videoInfo.url);
    if (alreadyInQueue) {
        showStatus(vda, vda.t('alreadyInQueue') || 'Video is already in the queue', 'error');
        return;
    }

    const downloadBtn = document.getElementById('download-btn');
    const btnText = document.getElementById('download-btn-text');
    const spinner = document.getElementById('download-spinner');
    const statusDiv = document.getElementById('download-status');
    const messageElement = document.getElementById('status-message-text');

    downloadBtn.disabled = true;
    btnText.textContent = vda.t('downloading') || 'Downloading...';
    spinner.style.display = 'block';
    statusDiv.style.display = 'block';

    const quality = document.getElementById('quality-select').value;
    const format = document.getElementById('format-select').value;
    const isYouTube = vda.isYouTubeDomain(vda.videoInfo.url);

    try {
        const res = await fetch(`http://${vda.serverIp}:${vda.serverPort}/downloadV2`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: vda.videoInfo.url,
                quality,
                format,
                output_path: vda.downloadFolder,
                use_firefox_cookies: isYouTube
            })
        });

        const data = await res.json();

        if (res.ok && data.success) {
       const messageElement = document.getElementById('status-message-text');
       messageElement.textContent = `Dodano do kolejki pobierania id: ${data.id}`;
       document.getElementById('download-btn').style.display = 'none';
     } else {
            showStatus(vda, data.error || vda.t('downloadFailed') || 'Download Failed', 'error');
            downloadBtn.disabled = false;
            btnText.textContent = vda.t('downloadVideo') || 'Download Video';
            spinner.style.display = 'none';
        }
    } catch (e) {
        console.error(e);
        showStatus(vda, vda.t('serverNotRunning') || 'Server not running', 'error');
        downloadBtn.disabled = false;
        btnText.textContent = vda.t('downloadVideo') || 'Download Video';
        spinner.style.display = 'none';
    }
}

