/* ============================================================
   Whisper Studio — Frontend JavaScript
   Full functionality: upload, transcribe, export, history, etc.
   ============================================================ */

'use strict';

const API = '';  // same origin

// ── State ──────────────────────────────────────────────────────
let state = {
  selectedFile: null,
  selectedModel: 'turbo',
  currentJobId: null,
  currentResult: null,
  eventSource: null,
};

// ── DOM Refs ────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// ── Init ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initNavTabs();
  initUpload();
  loadModels();
  loadLanguages();
  initTaskRadio();
  initAdvancedPanel();
  initResultActions();
  initExportDropdown();
  checkHealth();
  setInterval(checkHealth, 30000);
});

// ── Navigation Tabs ─────────────────────────────────────────────
function initNavTabs() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('.tab-content').forEach(p => {
        p.classList.remove('active');
        p.classList.add('hidden');
      });
      const page = $(`page-${target}`);
      page.classList.remove('hidden');
      page.classList.add('active');

      if (target === 'history') loadHistory();
      if (target === 'about') loadSystemStatus();
    });
  });
}

// ── Upload ──────────────────────────────────────────────────────
function initUpload() {
  const zone = $('uploadZone');
  const input = $('fileInput');
  const browseBtn = $('browseBtn');
  const removeBtn = $('removeFile');

  browseBtn.addEventListener('click', () => input.click());
  zone.addEventListener('click', e => {
    if (e.target !== browseBtn) input.click();
  });

  input.addEventListener('change', () => {
    if (input.files[0]) handleFile(input.files[0]);
  });

  // Drag and drop
  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  removeBtn.addEventListener('click', clearFile);
}

function handleFile(file) {
  const SUPPORTED = ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm', '.ogg', '.flac'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!SUPPORTED.includes(ext)) {
    toast(`Unsupported format: ${ext}`, 'error');
    return;
  }

  state.selectedFile = file;
  $('fileName').textContent = file.name;
  $('fileSize').textContent = formatBytes(file.size);
  $('uploadZone').classList.add('hidden');
  $('filePreview').classList.remove('hidden');

  // Setup audio preview
  const player = $('audioPlayer');
  player.src = URL.createObjectURL(file);

  updateTranscribeBtn();
}

function clearFile() {
  state.selectedFile = null;
  $('fileInput').value = '';
  $('uploadZone').classList.remove('hidden');
  $('filePreview').classList.add('hidden');
  $('audioPlayer').src = '';
  updateTranscribeBtn();
}

function updateTranscribeBtn() {
  $('transcribeBtn').disabled = !state.selectedFile;
}

// ── Models ──────────────────────────────────────────────────────
async function loadModels() {
  try {
    const res = await fetch(`${API}/api/models`);
    const data = await res.json();
    renderModels(data.models);
  } catch {
    // Fallback to hardcoded
    renderModels([
      {id:'tiny',name:'Tiny',speed:'~10x'},
      {id:'base',name:'Base',speed:'~7x'},
      {id:'small',name:'Small',speed:'~4x'},
      {id:'medium',name:'Medium',speed:'~2x'},
      {id:'large',name:'Large',speed:'1x'},
      {id:'turbo',name:'Turbo',speed:'~8x'},
    ]);
  }
}

function renderModels(models) {
  const grid = $('modelGrid');
  grid.innerHTML = models.map(m => `
    <button class="model-btn ${m.id === state.selectedModel ? 'active' : ''}"
            data-model="${m.id}" title="${m.description || ''}">
      <span class="model-name">${m.name}</span>
      <span class="model-speed">${m.speed || ''}</span>
    </button>
  `).join('');

  grid.querySelectorAll('.model-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      grid.querySelectorAll('.model-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.selectedModel = btn.dataset.model;
    });
  });
}

// ── Languages ───────────────────────────────────────────────────
async function loadLanguages() {
  try {
    const res = await fetch(`${API}/api/languages`);
    const data = await res.json();
    renderLanguages(data.languages);
  } catch {
    renderLanguages([{code:'auto', name:'Auto Detect'}, {code:'en', name:'English'}, {code:'vi', name:'Vietnamese'}]);
  }
}

function renderLanguages(langs) {
  const sel = $('langSelect');
  sel.innerHTML = langs.map(l =>
    `<option value="${l.code}">${l.name}${l.code === 'auto' ? '' : ` (${l.code})`}</option>`
  ).join('');
}

// ── Task Radio ──────────────────────────────────────────────────
function initTaskRadio() {
  document.querySelectorAll('input[name="task"]').forEach(radio => {
    radio.addEventListener('change', () => {
      document.querySelectorAll('.radio-btn').forEach(btn => btn.classList.remove('active'));
      radio.closest('.radio-btn').classList.add('active');
    });
  });
}

// ── Advanced Panel ──────────────────────────────────────────────
function initAdvancedPanel() {
  const toggle = $('advancedToggle');
  const panel = $('advancedPanel');
  const arrow = toggle.querySelector('.toggle-arrow');

  toggle.addEventListener('click', () => {
    panel.classList.toggle('hidden');
    arrow.classList.toggle('rotated');
  });

  const tempSlider = $('temperatureSlider');
  const tempVal = $('tempValue');
  tempSlider.addEventListener('input', () => {
    tempVal.textContent = parseFloat(tempSlider.value).toFixed(1);
  });
}

// ── Transcription ────────────────────────────────────────────────
$('transcribeBtn').addEventListener('click', startTranscription);

async function startTranscription() {
  if (!state.selectedFile) return;

  // Build form data
  const form = new FormData();
  form.append('audio', state.selectedFile);
  form.append('model', state.selectedModel);
  form.append('language', $('langSelect').value);
  form.append('task', document.querySelector('input[name="task"]:checked').value);
  form.append('word_timestamps', $('wordTimestamps').checked ? 'true' : 'false');
  form.append('temperature', $('temperatureSlider').value);

  // Show progress UI
  showProgress();

  try {
    const res = await fetch(`${API}/api/transcribe`, { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Upload failed');
    }
    const data = await res.json();
    state.currentJobId = data.job_id;
    startPolling(data.job_id);
  } catch (err) {
    showError(err.message);
  }
}

// ── Progress Streaming ───────────────────────────────────────────
function startPolling(jobId) {
  // Clean up previous EventSource
  if (state.eventSource) {
    state.eventSource.close();
  }

  const es = new EventSource(`${API}/api/job/${jobId}/stream`);
  state.eventSource = es;

  es.onmessage = (e) => {
    const job = JSON.parse(e.data);
    updateProgress(job);
    if (job.status === 'completed') {
      es.close();
      state.currentResult = job.result;
      showResult(job.result);
    } else if (job.status === 'failed') {
      es.close();
      showError(job.message || 'Transcription failed');
    }
  };

  es.onerror = () => {
    es.close();
    // Fallback to polling
    pollJobStatus(jobId);
  };
}

async function pollJobStatus(jobId, attempts = 0) {
  if (attempts > 120) {
    showError('Timeout: transcription took too long');
    return;
  }
  try {
    const res = await fetch(`${API}/api/job/${jobId}`);
    const job = await res.json();
    updateProgress(job);
    if (job.status === 'completed') {
      state.currentResult = job.result;
      showResult(job.result);
    } else if (job.status === 'failed') {
      showError(job.message || 'Transcription failed');
    } else {
      setTimeout(() => pollJobStatus(jobId, attempts + 1), 1000);
    }
  } catch {
    setTimeout(() => pollJobStatus(jobId, attempts + 1), 2000);
  }
}

// ── UI State Transitions ─────────────────────────────────────────
function showProgress() {
  $('resultIdle').classList.add('hidden');
  $('resultContent').classList.add('hidden');
  $('resultError').classList.add('hidden');
  $('resultProgress').classList.remove('hidden');
  updateProgress({ progress: 5, message: 'Uploading...' });
}

function updateProgress(job) {
  $('progressTitle').textContent = job.status === 'queued' ? 'Queued' : 'Processing...';
  $('progressFill').style.width = `${job.progress || 0}%`;
  $('progressPercent').textContent = `${job.progress || 0}%`;
  $('progressMsg').textContent = job.message || '...';
}

function showResult(result) {
  $('resultProgress').classList.add('hidden');
  $('resultContent').classList.remove('hidden');

  // Badges
  $('resultLang').textContent = `🌐 ${capitalizeFirst(result.language || 'unknown')}`;
  $('resultModel').textContent = `⚡ ${result.model || ''}`;
  $('resultDuration').textContent = `⏱ ${result.duration}s`;

  // Full text
  $('transcriptBox').textContent = result.text || '(No speech detected)';

  // Segments
  renderSegments(result.segments || []);

  toast('Transcription complete!', 'success');
}

function renderSegments(segments) {
  const list = $('segmentsList');
  if (!segments.length) {
    list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem">No segments available</p>';
    return;
  }
  list.innerHTML = segments.map(seg => `
    <div class="segment-item">
      <div class="segment-time">${formatTime(seg.start)} → ${formatTime(seg.end)}</div>
      <div class="segment-text">${escHtml(seg.text)}</div>
    </div>
  `).join('');
}

function showError(msg) {
  $('resultProgress').classList.add('hidden');
  $('resultContent').classList.add('hidden');
  $('resultError').classList.remove('hidden');
  $('errorMsg').textContent = msg;
  toast(`Error: ${msg}`, 'error');
}

// ── Result Actions ───────────────────────────────────────────────
function initResultActions() {
  // View tabs
  document.querySelectorAll('.view-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const view = tab.dataset.view;
      $('textView').classList.toggle('hidden', view !== 'text');
      $('segmentsView').classList.toggle('hidden', view !== 'segments');
    });
  });

  // Copy button
  $('copyBtn').addEventListener('click', () => {
    if (!state.currentResult) return;
    navigator.clipboard.writeText(state.currentResult.text).then(() => {
      toast('Copied to clipboard!', 'success');
    });
  });

  // Retry
  $('retryBtn').addEventListener('click', () => {
    $('resultError').classList.add('hidden');
    $('resultIdle').classList.remove('hidden');
  });

  // Refresh history
  $('refreshHistory').addEventListener('click', loadHistory);
  $('refreshStatus').addEventListener('click', loadSystemStatus);
}

// ── Export Dropdown ──────────────────────────────────────────────
function initExportDropdown() {
  const btn = $('exportBtn');
  const menu = $('exportMenu');

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('hidden');
  });

  document.addEventListener('click', () => menu.classList.add('hidden'));

  menu.querySelectorAll('.dropdown-item').forEach(item => {
    item.addEventListener('click', () => {
      const fmt = item.dataset.fmt;
      exportResult(fmt);
      menu.classList.add('hidden');
    });
  });
}

async function exportResult(fmt) {
  if (!state.currentResult) {
    toast('No result to export', 'error');
    return;
  }

  try {
    const res = await fetch(`${API}/api/export/${fmt}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ result: state.currentResult })
    });

    if (!res.ok) throw new Error('Export failed');

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcription.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
    toast(`Exported as .${fmt}`, 'success');
  } catch (err) {
    toast(`Export failed: ${err.message}`, 'error');
  }
}

// ── History ──────────────────────────────────────────────────────
async function loadHistory() {
  const list = $('historyList');
  list.innerHTML = '<p style="color:var(--text-muted);padding:2rem;text-align:center">Loading...</p>';
  try {
    const res = await fetch(`${API}/api/jobs`);
    const data = await res.json();
    renderHistory(data.jobs || []);
  } catch {
    list.innerHTML = '<p style="color:var(--text-muted);padding:2rem;text-align:center">Failed to load history</p>';
  }
}

function renderHistory(jobs) {
  const list = $('historyList');
  if (!jobs.length) {
    list.innerHTML = `
      <div class="empty-state" style="text-align:center;padding:3rem;color:var(--text-muted)">
        <div style="font-size:3rem;margin-bottom:1rem">📋</div>
        <p>No transcriptions yet</p>
      </div>`;
    return;
  }

  list.innerHTML = jobs.map(job => {
    const preview = job.result?.text ? job.result.text.slice(0, 120) + '…' : '';
    const date = new Date(job.created_at * 1000).toLocaleString();
    const model = job.options?.model || '–';
    const lang = job.result?.language ? capitalizeFirst(job.result.language) : '–';
    const duration = job.result?.duration ? `${job.result.duration}s` : '–';

    return `
      <div class="history-item" data-job="${job.id}">
        <div>
          <div class="history-file">${escHtml(job.filename || 'Unknown file')}</div>
          <div class="history-meta">📅 ${date} &nbsp;·&nbsp; ⚡ ${model} &nbsp;·&nbsp; 🌐 ${lang} &nbsp;·&nbsp; ⏱ ${duration}</div>
          ${preview ? `<div class="history-preview">${escHtml(preview)}</div>` : ''}
        </div>
        <div class="history-right">
          <span class="status-pill status-${job.status}">${job.status}</span>
        </div>
      </div>`;
  }).join('');

  // Click to view
  list.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => {
      const job = jobs.find(j => j.id === item.dataset.job);
      if (job?.result) viewHistoryJob(job);
    });
  });
}

function viewHistoryJob(job) {
  // Switch to transcribe tab and show result
  $('tab-transcribe').click();
  state.currentResult = job.result;
  $('resultIdle').classList.add('hidden');
  $('resultProgress').classList.add('hidden');
  $('resultError').classList.add('hidden');
  showResult(job.result);
  toast('Loaded from history', 'info');
}

// ── System Status ─────────────────────────────────────────────────
async function loadSystemStatus() {
  try {
    const res = await fetch(`${API}/api/health`);
    const data = await res.json();

    $('sysBackend').textContent = data.status === 'ok' ? '✓ Online' : '✗ Error';
    $('sysBackend').className = `badge ${data.status === 'ok' ? 'badge-success' : 'badge-error'}`;
    $('sysWhisper').textContent = data.whisper_version || '–';
    $('sysWhisper').className = 'badge badge-info';
    $('sysTorch').textContent = data.torch_version || '–';
    $('sysTorch').className = 'badge badge-info';
    $('sysDevice').textContent = (data.device || '–').toUpperCase();
    $('sysDevice').className = `badge ${data.device === 'cuda' ? 'badge-success' : 'badge-muted'}`;
    $('sysCuda').textContent = data.cuda_available ? '✓ Available' : '✗ Not available';
    $('sysCuda').className = `badge ${data.cuda_available ? 'badge-success' : 'badge-muted'}`;

    const models = data.loaded_models?.length ? data.loaded_models.join(', ') : 'None';
    $('sysModels').textContent = models;
    $('sysModels').className = 'badge badge-muted';
  } catch {
    $('sysBackend').textContent = '✗ Offline';
    $('sysBackend').className = 'badge badge-error';
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API}/api/health`);
    const data = await res.json();
    const dot = $('statusDot');
    const txt = $('statusText');
    if (data.status === 'ok') {
      dot.className = 'status-dot online';
      txt.textContent = `Online · ${data.device?.toUpperCase() || 'CPU'}`;
    } else {
      dot.className = 'status-dot offline';
      txt.textContent = 'Error';
    }
  } catch {
    $('statusDot').className = 'status-dot offline';
    $('statusText').textContent = 'Offline';
  }
}

// ── Toasts ───────────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  $('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Utilities ────────────────────────────────────────────────────
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatTime(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  const ms = Math.round((secs % 1) * 10);
  return h > 0
    ? `${h}:${pad(m)}:${pad(s)}.${ms}`
    : `${pad(m)}:${pad(s)}.${ms}`;
}

function pad(n) { return String(n).padStart(2, '0'); }

function capitalizeFirst(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
