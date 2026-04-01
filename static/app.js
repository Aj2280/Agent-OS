// ═══ DOM ═══
const chatMessages = document.getElementById('chat-messages');
const chatScroll = document.getElementById('chat-scroll');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');
const thinkingIndicator = document.getElementById('thinking-indicator');
const resetBtn = document.getElementById('reset-btn');
const statusText = document.getElementById('status-text');
const previewIframe = document.getElementById('preview-iframe');
const previewEmpty = document.getElementById('preview-empty');
const previewFilename = document.getElementById('preview-filename');
const codeViewer = document.getElementById('code-viewer');
const outputViewer = document.getElementById('output-viewer');
const attachmentStrip = document.getElementById('attachment-strip');
const fileInput = document.getElementById('file-input');
const photoInput = document.getElementById('photo-input');

let lastPreviewFile = null;
let pendingAttachments = []; // {file, name, type, preview}

if (typeof marked !== 'undefined') marked.setOptions({ breaks: true, gfm: true });

// ═══ NAVIGATION ═══
document.querySelectorAll('.nav-item[data-view]').forEach(item => {
    item.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active-view'));
        document.getElementById(`view-${item.dataset.view}`)?.classList.add('active-view');
        if (item.dataset.view === 'workspace') loadWorkspace();
        if (item.dataset.view === 'settings') loadProviderStatus();
    });
});

// ═══ PREVIEW TABS ═══
document.querySelectorAll('.preview-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.preview-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active-tab'));
        tab.classList.add('active');
        document.getElementById(`tab-${tab.dataset.tab}`)?.classList.add('active-tab');
    });
});

// ═══════════════════════════════════
// FILE / PHOTO ATTACHMENTS
// ═══════════════════════════════════
document.getElementById('attach-file-btn').addEventListener('click', () => fileInput.click());
document.getElementById('attach-photo-btn').addEventListener('click', () => photoInput.click());

fileInput.addEventListener('change', (e) => handleFileSelect(e.target.files));
photoInput.addEventListener('change', (e) => handleFileSelect(e.target.files));

function handleFileSelect(files) {
    for (const file of files) {
        const attachment = { file, name: file.name, type: file.type, preview: null };

        // Generate preview for images
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => {
                attachment.preview = e.target.result;
                renderAttachments();
            };
            reader.readAsDataURL(file);
        }

        pendingAttachments.push(attachment);
    }
    renderAttachments();
    fileInput.value = '';
    photoInput.value = '';
}

function renderAttachments() {
    if (pendingAttachments.length === 0) {
        attachmentStrip.classList.add('hidden');
        attachmentStrip.innerHTML = '';
        return;
    }
    attachmentStrip.classList.remove('hidden');
    attachmentStrip.innerHTML = '';
    pendingAttachments.forEach((att, i) => {
        const chip = document.createElement('div');
        chip.className = 'attachment-chip';
        const icon = att.type.startsWith('image/') ? '🖼️' : '📄';
        const imgTag = att.preview ? `<img src="${att.preview}" alt="preview">` : '';
        chip.innerHTML = `${imgTag}<span>${icon} ${att.name}</span><span class="remove-chip" data-idx="${i}">✕</span>`;
        attachmentStrip.appendChild(chip);
    });
    // Remove handler
    attachmentStrip.querySelectorAll('.remove-chip').forEach(btn => {
        btn.addEventListener('click', (e) => {
            pendingAttachments.splice(parseInt(e.target.dataset.idx), 1);
            renderAttachments();
        });
    });
}

async function uploadAttachments() {
    const uploaded = [];
    for (const att of pendingAttachments) {
        try {
            const formData = new FormData();
            formData.append('file', att.file);
            const res = await fetch('/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.status === 'ok') {
                uploaded.push(data.filename);
            }
        } catch (e) {
            console.error('Upload failed:', att.name, e);
        }
    }
    pendingAttachments = [];
    renderAttachments();
    return uploaded;
}

// ═══════════════════════════════════
// CAMERA
// ═══════════════════════════════════
const cameraModal = document.getElementById('camera-modal');
const cameraVideo = document.getElementById('camera-video');
const cameraCanvas = document.getElementById('camera-canvas');
let cameraStream = null;
let facingMode = 'user';

document.getElementById('camera-btn').addEventListener('click', openCamera);
document.getElementById('camera-close').addEventListener('click', closeCamera);
document.getElementById('capture-btn').addEventListener('click', capturePhoto);
document.getElementById('switch-camera-btn').addEventListener('click', switchCamera);

async function openCamera() {
    cameraModal.classList.remove('hidden');
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: facingMode, width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: false
        });
        cameraVideo.srcObject = cameraStream;
    } catch (e) {
        alert('Camera access denied or not available.');
        closeCamera();
    }
}

function closeCamera() {
    cameraModal.classList.add('hidden');
    if (cameraStream) {
        cameraStream.getTracks().forEach(t => t.stop());
        cameraStream = null;
    }
}

async function switchCamera() {
    facingMode = facingMode === 'user' ? 'environment' : 'user';
    closeCamera();
    await openCamera();
}

async function capturePhoto() {
    cameraCanvas.width = cameraVideo.videoWidth;
    cameraCanvas.height = cameraVideo.videoHeight;
    const ctx = cameraCanvas.getContext('2d');
    ctx.drawImage(cameraVideo, 0, 0);
    const dataUrl = cameraCanvas.toDataURL('image/png');

    // Upload to server
    const timestamp = Date.now();
    const filename = `camera_${timestamp}.png`;
    try {
        const res = await fetch('/upload-base64', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: dataUrl, filename })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            // Add as attachment chip
            pendingAttachments.push({
                file: null, name: filename, type: 'image/png', preview: dataUrl
            });
            renderAttachments();
        }
    } catch (e) {
        console.error('Camera upload failed', e);
    }

    closeCamera();
}

// ═══ CHAT ═══
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message && pendingAttachments.length === 0) return;

    // Upload attachments first
    let uploadedFiles = [];
    if (pendingAttachments.length > 0) {
        uploadedFiles = await uploadAttachments();
    }

    // Build message with file context
    let fullMessage = message;
    if (uploadedFiles.length > 0) {
        const fileList = uploadedFiles.map(f => `- ${f}`).join('\n');
        fullMessage += `\n\n[Attached files uploaded to workspace:\n${fileList}]`;
    }

    appendMessage('user', message || `📎 ${uploadedFiles.join(', ')}`);
    userInput.value = '';
    userInput.style.height = 'auto';
    showThinking(true);

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: fullMessage, model: modelSelect.value })
        });
        const data = await res.json();

        if (data.error) {
            appendMessage('agent', `❌ Error: ${data.error}`);
        } else {
            appendMessage('agent', data.response, true);
        }

        if (data.logs?.length > 0) handleToolLogs(data.logs);
        if (data.created_files?.length > 0) showCreatedFiles(data.created_files);
        if (data.preview_file) loadPreview(data.preview_file);
    } catch (e) {
        appendMessage('agent', '❌ Connection error.');
    } finally {
        showThinking(false);
    }
}

function quickAction(text) { userInput.value = text; sendMessage(); }

function appendMessage(role, text, useMarkdown = false) {
    const welcome = chatMessages.querySelector('.welcome-card');
    if (welcome) welcome.remove();
    const div = document.createElement('div');
    div.classList.add('message', role);
    if (useMarkdown && role === 'agent' && typeof marked !== 'undefined') {
        div.innerHTML = marked.parse(text || '');
    } else {
        div.textContent = text || '';
    }
    chatMessages.appendChild(div);
    chatScroll.scrollTop = chatScroll.scrollHeight;
}

function handleToolLogs(logs) {
    let output = '';
    logs.forEach(log => {
        const icon = log.status === 'success' ? '✅' : '❌';
        output += `${icon} ${log.name}(${JSON.stringify(log.args).substring(0, 100)})\n`;
        if (log.result) output += `   → ${log.result.substring(0, 200)}\n`;
        output += '\n';
    });
    outputViewer.textContent = output;
}

function showCreatedFiles(files) {
    files.forEach(file => {
        const badge = document.createElement('div');
        badge.className = 'file-badge';
        badge.innerHTML = `📄 ${file} <span style="opacity:0.5">(click to preview)</span>`;
        badge.onclick = () => file.endsWith('.html') ? loadPreview(file) : loadCodeView(file);
        chatMessages.appendChild(badge);
    });
    chatScroll.scrollTop = chatScroll.scrollHeight;
}

function loadPreview(filename) {
    lastPreviewFile = filename;
    previewFilename.textContent = filename;
    previewEmpty.classList.add('hidden');
    previewIframe.classList.remove('hidden');
    previewIframe.src = `/preview/${filename}`;
    switchPreviewTab('preview');
}

async function loadCodeView(filename) {
    try {
        const res = await fetch(`/workspace-file/${filename}`);
        const data = await res.json();
        codeViewer.textContent = data.content || 'No content';
        previewFilename.textContent = filename;
        switchPreviewTab('code');
    } catch (e) { codeViewer.textContent = 'Error loading'; }
}

function switchPreviewTab(tab) {
    document.querySelectorAll('.preview-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active-tab'));
    document.querySelector(`[data-tab="${tab}"]`)?.classList.add('active');
    document.getElementById(`tab-${tab}`)?.classList.add('active-tab');
}

document.getElementById('open-new-tab')?.addEventListener('click', () => {
    if (lastPreviewFile) window.open(`/preview/${lastPreviewFile}`, '_blank');
});

function showThinking(show) {
    thinkingIndicator.classList.toggle('hidden', !show);
    statusText.textContent = show ? 'Working...' : 'Online';
    sendBtn.disabled = show;
}

// ═══ PROVIDER SETTINGS ═══
async function saveProviderKey(provider) {
    const input = document.getElementById(`key-${provider}`);
    const key = input?.value.trim();
    if (!key) return alert('Enter an API key.');
    try {
        const res = await fetch('/set-provider-key', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, api_key: key })
        });
        const data = await res.json();
        alert(data.message || 'Saved!');
        input.value = '';
        loadProviderStatus();
        loadProviders();
    } catch (e) { alert('Error saving.'); }
}
window.saveProviderKey = saveProviderKey;

async function loadProviderStatus() {
    try {
        const res = await fetch('/providers');
        const providers = await res.json();
        for (const [pid, pdata] of Object.entries(providers)) {
            if (pid === '_custom_models') continue;
            const dot = document.getElementById(`status-${pid}`);
            if (dot) {
                dot.classList.toggle('connected', pdata.has_key || !pdata.needs_key);
            }
        }
    } catch (e) { }
}

async function loadProviders() {
    try {
        const res = await fetch('/providers');
        const providers = await res.json();
        modelSelect.innerHTML = '';
        for (const [pid, pdata] of Object.entries(providers)) {
            if (pid === '_custom_models') continue;
            const group = document.createElement('optgroup');
            group.label = `${pdata.name} ${pdata.has_key || !pdata.needs_key ? '✓' : '⚠️'}`;
            pdata.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = `${pdata.prefix}${m.id}`;
                opt.textContent = m.name;
                if (!pdata.has_key && pdata.needs_key) {
                    opt.disabled = true;
                    opt.textContent += ' (no key)';
                }
                group.appendChild(opt);
            });
            modelSelect.appendChild(group);
        }
        const customs = providers._custom_models || [];
        if (customs.length > 0) {
            const g = document.createElement('optgroup');
            g.label = 'Custom';
            customs.forEach(m => {
                const p = providers[m.provider];
                const opt = document.createElement('option');
                opt.value = `${p?.prefix || ''}${m.id}`;
                opt.textContent = m.name;
                g.appendChild(opt);
            });
            modelSelect.appendChild(g);
        }
        for (const opt of modelSelect.options) {
            if (!opt.disabled) { modelSelect.value = opt.value; break; }
        }
    } catch (e) { }
}

document.getElementById('add-model-btn')?.addEventListener('click', async () => {
    const provider = document.getElementById('custom-provider').value;
    const modelId = document.getElementById('custom-model-id').value.trim();
    const modelName = document.getElementById('custom-model-name').value.trim() || modelId;
    if (!modelId) return alert('Enter model ID.');
    try {
        await fetch('/add-custom-model', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, model_id: modelId, model_name: modelName })
        });
        document.getElementById('custom-model-id').value = '';
        document.getElementById('custom-model-name').value = '';
        alert(`Model "${modelName}" added!`);
        loadProviders();
    } catch (e) { alert('Error.'); }
});

document.getElementById('save-prompt-btn')?.addEventListener('click', async () => {
    const prompt = document.getElementById('system-prompt-input').value.trim();
    try {
        await fetch('/update-config', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ system_prompt: prompt })
        });
        alert('System prompt saved!');
    } catch (e) { alert('Error.'); }
});

// ═══ WORKSPACE ═══
async function loadWorkspace() {
    const list = document.getElementById('ws-file-list');
    list.innerHTML = '<div class="empty-state"><span>⏳</span><p>Loading...</p></div>';
    try {
        const res = await fetch('/workspace-files');
        const data = await res.json();
        list.innerHTML = '';
        if (!data.files?.length) {
            list.innerHTML = '<div class="empty-state"><span>📂</span><p>Empty workspace.</p></div>';
            return;
        }
        data.files.forEach(f => {
            const item = document.createElement('div');
            item.className = 'file-item';
            const icons = { '.html': '🌐', '.py': '🐍', '.js': '📜', '.css': '🎨', '.json': '📋', '.md': '📝', '.png': '🖼️', '.jpg': '🖼️', '.jpeg': '🖼️', '.gif': '🖼️', '.webp': '🖼️' };
            const icon = f.is_dir ? '📁' : (icons[f.ext] || '📄');
            const size = f.is_dir ? '' : (f.size < 1024 ? f.size + 'B' : (f.size / 1024).toFixed(1) + 'KB');
            item.innerHTML = `<span class="f-icon">${icon}</span><span class="f-name">${f.name}</span><span class="f-size">${size}</span>`;
            item.onclick = () => {
                if (f.name.endsWith('.html')) loadPreview(f.name);
                else if (f.ext && ['.png', '.jpg', '.jpeg', '.gif', '.webp'].includes(f.ext)) {
                    // Show image preview
                    previewEmpty.classList.add('hidden');
                    previewIframe.classList.remove('hidden');
                    previewIframe.src = `/preview/${f.name}`;
                    previewFilename.textContent = f.name;
                    switchPreviewTab('preview');
                } else {
                    loadCodeView(f.name);
                }
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                document.querySelector('[data-view="chat"]').classList.add('active');
                document.querySelectorAll('.view').forEach(v => v.classList.remove('active-view'));
                document.getElementById('view-chat').classList.add('active-view');
            };
            list.appendChild(item);
        });
    } catch (e) {
        list.innerHTML = '<div class="empty-state"><span>❌</span><p>Error.</p></div>';
    }
}
document.getElementById('refresh-ws')?.addEventListener('click', loadWorkspace);

// ═══ RESET ═══
resetBtn.addEventListener('click', async () => {
    try {
        await fetch('/reset', { method: 'POST' });
        chatMessages.innerHTML = `<div class="welcome-card"><div class="welcome-icon">🧠</div><h2>New Session</h2><p>Ready. What do you want to create?</p></div>`;
        previewIframe.classList.add('hidden');
        previewEmpty.classList.remove('hidden');
        previewFilename.textContent = 'No file';
        outputViewer.textContent = 'Output will appear here.';
        codeViewer.textContent = '// Code appears here';
        lastPreviewFile = null;
        pendingAttachments = [];
        renderAttachments();
    } catch (e) { }
});

// ═══ INPUT ═══
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
userInput.addEventListener('input', () => {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 100) + 'px';
});

// Drag & drop files
const leftPanel = document.querySelector('.left-panel');
leftPanel.addEventListener('dragover', (e) => { e.preventDefault(); e.stopPropagation(); });
leftPanel.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files);
});

// ═══ INIT ═══
loadProviders();
loadProviderStatus();
