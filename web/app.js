/* ============================================================
   AI Document Assistant — Frontend controller
   Bridges the UI with the Python backend exposed via
   window.pywebview.api. Falls back to a demo mode when opened
   in a plain browser (no pywebview), so the UI can be previewed.
   ============================================================ */

const PAGE_META = {
  dashboard: { title: 'หน้าหลัก', sub: 'ภาพรวมการทำงานของระบบ' },
  process:   { title: 'ประมวลผลเอกสาร', sub: 'ตรวจสอบและจัดเก็บเอกสารยืนยันการเบิกเงินกู้' },
  history:   { title: 'ประวัติการทำงาน', sub: 'ผลการประมวลผลย้อนหลัง' },
  settings:  { title: 'ตั้งค่า', sub: 'กำหนดค่าการเชื่อมต่อและข้อมูลระบบ' },
};

const state = {
  config: { api_key: '', source_dir: '', output_dir: '', prompt: '', font_scale: 1.0 },
  results: [],
  logs: [],
  filter: 'all',
  search: '',
  pageSize: 10,
  currentPage: 1,
  totalFiles: 0,
  processing: false,
  history: null,          // full run history used to build the dashboard
  dashRange: '7d',        // dashboard time filter: today | 7d | 30d | all
  dashSelectedBar: null,  // { day, type } selected by clicking an individual chart bar
  sessionCounted: true,
  elapsedSeconds: 0,
  promptVersions: [],
};

function isPageActive(page) {
  const el = document.getElementById('page-' + page);
  return !!el && el.classList.contains('active');
}

const LOG_STEP_LEVEL_LABEL = { info: 'กำลังดำเนินการ', success: 'สำเร็จ', warning: 'คำเตือน', error: 'ข้อผิดพลาด' };
const MAX_LOG_ENTRIES = 300;

const $ = (id) => document.getElementById(id);
const hasApi = () => window.pywebview && window.pywebview.api;

/* ---------- API wrapper (with demo fallback) ---------- */
const api = {
  async call(name, ...args) {
    if (hasApi() && typeof window.pywebview.api[name] === 'function') {
      return await window.pywebview.api[name](...args);
    }
    return demo(name, args);
  },
};

function demo(name, args) {
  switch (name) {
    case 'get_config': return { ...state.config };
    case 'pick_folder': return 'D:/กยศ/เอกสารรอตรวจ';
    case 'save_config': return { ...state.config, ...args[0] };
    case 'get_default_prompt': return state.config.prompt || '(โหมดตัวอย่าง: ไม่มีพร็อมท์เริ่มต้น)';
    case 'test_connection': return { ok: false, message: 'โหมดตัวอย่าง: ยังไม่ได้เชื่อมต่อ Python' };
    case 'count_documents': return { folders: 3, documents: 20 };
    case 'get_history': return [];
    case 'get_dashboard': return { total: 0, success: 0, manual: 0, rate: 0, chart: [], recent: [] };
    case 'get_prompt_versions': return [];
    case 'reveal_file_or_folder':
      toast(`[โหมดตัวอย่าง] เปิดพาธ: output_dir/${args[0] || ''}`, 'ok');
      return { ok: true };
    default: return null;
  }
}

/* ---------- Navigation ---------- */
function goto(page) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.page === page));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  $('page-' + page).classList.add('active');
  const meta = PAGE_META[page];
  $('pageTitle').textContent = meta.title;
  $('pageSubtitle').textContent = meta.sub;
  if (page === 'dashboard') loadDashboard();
  if (page === 'history') loadHistory();
}

document.querySelectorAll('[data-page]').forEach(el => {
  el.addEventListener('click', () => goto(el.dataset.page));
});

$('toggleSidebar').addEventListener('click', () => {
  document.querySelector('.app').classList.toggle('collapsed');
});

/* ---------- Font Scale ---------- */
const FONT_SCALE_LEVELS = [0.85, 1.0, 1.15, 1.30];

function applyFontScale(scale) {
  scale = parseFloat(scale) || 1.0;
  if (!FONT_SCALE_LEVELS.includes(scale)) {
    scale = FONT_SCALE_LEVELS.reduce((prev, curr) => 
      Math.abs(curr - scale) < Math.abs(prev - scale) ? curr : prev
    );
  }
  document.documentElement.style.setProperty('--font-scale', scale);
  state.config.font_scale = scale;

  const labelEl = $('fontScaleLabel');
  if (labelEl) {
    labelEl.textContent = `${Math.round(scale * 100)}%`;
  }
}

function stepFontScale(direction) {
  const current = FONT_SCALE_LEVELS.includes(state.config.font_scale) ? state.config.font_scale : 1.0;
  const idx = FONT_SCALE_LEVELS.indexOf(current);
  const nextIdx = Math.min(FONT_SCALE_LEVELS.length - 1, Math.max(0, idx + direction));
  const nextScale = FONT_SCALE_LEVELS[nextIdx];
  applyFontScale(nextScale);
  api.call('save_config', { font_scale: nextScale });
  toast(`ปรับขนาดตัวอักษรเป็น ${Math.round(nextScale * 100)}%`, 'ok');
}

const fontDecreaseBtn = $('fontDecreaseBtn');
if (fontDecreaseBtn) fontDecreaseBtn.addEventListener('click', () => stepFontScale(-1));
const fontIncreaseBtn = $('fontIncreaseBtn');
if (fontIncreaseBtn) fontIncreaseBtn.addEventListener('click', () => stepFontScale(1));

/* ---------- Toast ---------- */
let toastTimer;
function toast(msg, type = '') {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = 'toast'; }, 3000);
}

/* ---------- Config load / bind ---------- */
async function loadConfig() {
  const cfg = await api.call('get_config');
  state.config = { ...state.config, ...cfg };
  applyFontScale(state.config.font_scale || 1.0);
  $('apiKey').value = state.config.api_key || '';
  $('setSource').value = state.config.source_dir || '';
  $('setOutput').value = state.config.output_dir || '';
  $('promptText').value = state.config.prompt || '';
  refreshFolderCards();
  await refreshFileCount();
}

function refreshFolderCards() {
  $('srcPath').textContent = state.config.source_dir || 'ยังไม่ได้เลือกโฟลเดอร์';
  $('outPath').textContent = state.config.output_dir || 'ยังไม่ได้เลือกโฟลเดอร์';
}

async function refreshFileCount() {
  if (!state.config.source_dir) { $('srcHint').textContent = ''; state.totalFiles = 0; updateMiniStats(); return; }
  const c = await api.call('count_documents', state.config.source_dir);
  state.totalFiles = c.documents || 0;
  $('srcHint').textContent = `พบ ${c.folders} โฟลเดอร์ ${c.documents} เอกสาร พร้อมประมวลผล`;
  updateMiniStats();
}

/* ---------- Folder pickers ---------- */
async function pickInto(target) {
  const path = await api.call('pick_folder');
  if (!path) return;
  state.config[target] = path;
  await api.call('save_config', { [target]: path });
  refreshFolderCards();
  $('setSource').value = state.config.source_dir || '';
  $('setOutput').value = state.config.output_dir || '';
  if (target === 'source_dir') await refreshFileCount();
}
$('pickSource').addEventListener('click', () => pickInto('source_dir'));
$('pickOutput').addEventListener('click', () => pickInto('output_dir'));
$('setPickSource').addEventListener('click', () => pickInto('source_dir'));
$('setPickOutput').addEventListener('click', () => pickInto('output_dir'));

/* ---------- Confirm modal ----------
   With a phrase -> type-to-confirm (destructive settings changes).
   Without a phrase (null) -> simple OK/Cancel confirmation dialog. */
function askConfirm(phrase, title, desc) {
  return new Promise((resolve) => {
    const overlay = $('confirmModal');
    const input = $('confirmInput');
    const okBtn = $('confirmOkBtn');
    const cancelBtn = $('confirmCancelBtn');
    const simple = !phrase;
    $('confirmTitle').textContent = title;
    $('confirmDesc').textContent = desc;
    $('confirmPhrase').textContent = phrase || '';
    $('confirmPhraseRow').hidden = simple;
    input.hidden = simple;
    input.value = '';
    okBtn.disabled = !simple;
    overlay.hidden = false;
    if (simple) { okBtn.focus(); } else { input.focus(); }

    function onInput() { okBtn.disabled = input.value.trim() !== phrase; }
    function onKeydown(e) {
      if (e.key === 'Enter' && !okBtn.disabled) { e.preventDefault(); onOk(); }
      if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
    }
    function cleanup() {
      overlay.hidden = true;
      input.removeEventListener('input', onInput);
      input.removeEventListener('keydown', onKeydown);
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
    }
    function onOk() { cleanup(); resolve(true); }
    function onCancel() { cleanup(); resolve(false); }

    input.addEventListener('input', onInput);
    input.addEventListener('keydown', onKeydown);
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
  });
}

/* ---------- Reset prompt to built-in default ---------- */
$('resetPromptBtn').addEventListener('click', async () => {
  const def = await api.call('get_default_prompt');
  $('promptText').value = def || '';
  toast('คืนค่าพร็อมท์เริ่มต้นแล้ว (ยังไม่บันทึก กด "บันทึกพร็อมท์" เพื่อยืนยัน)', 'ok');
});

/* ---------- Save prompt only (with confirm) ---------- */
$('savePromptBtn').addEventListener('click', async () => {
  const newPrompt = $('promptText').value;
  const promptChanged = newPrompt.trim() !== (state.config.prompt || '').trim();
  if (!promptChanged) { toast('พร็อมท์ยังไม่มีการเปลี่ยนแปลง', ''); return; }
  const ok = await askConfirm('confirm change prompt', 'ยืนยันการเปลี่ยนพร็อมท์',
    'คุณกำลังจะเปลี่ยนพร็อมท์ที่ใช้สั่งให้ AI อ่านและดึงข้อมูลจากเอกสาร');
  if (!ok) { toast('ยกเลิก: ไม่ได้ยืนยันการเปลี่ยนพร็อมท์', 'err'); return; }
  const cfg = { ...state.config, prompt: newPrompt };
  await api.call('save_config', cfg);
  state.config = { ...state.config, prompt: newPrompt };
  await loadPromptVersions();
  toast('บันทึกพร็อมท์เรียบร้อย ✓ (บันทึกเป็นเวอร์ชันใหม่แล้ว)', 'ok');
});

function cleanApiKey(str) {
  if (!str) return '';
  // 1. Remove zero-width characters and other hidden spaces
  let cleaned = str.replace(/[\u200B-\u200D\uFEFF]/g, '');
  // 2. Trim regular spaces/newlines
  cleaned = cleaned.trim();
  // 3. Remove surrounding single or double quotes (e.g. from env copy-paste)
  cleaned = cleaned.replace(/^['"]|['"]$/g, '');
  return cleaned.trim();
}

/* ---------- Settings save / test ---------- */
$('saveBtn').addEventListener('click', async () => {
  const cleanKey = cleanApiKey($('apiKey').value);
  $('apiKey').value = cleanKey;
  
  const newApiKey = cleanKey;
  const newPrompt = $('promptText').value;
  const newSource = $('setSource').value.trim();
  const newOutput = $('setOutput').value.trim();

  const apiChanged = newApiKey !== (state.config.api_key || '');
  const promptChanged = newPrompt.trim() !== (state.config.prompt || '').trim();

  if (apiChanged) {
    const ok = await askConfirm('confirm change api', 'ยืนยันการเปลี่ยนคีย์ API',
      'คุณกำลังจะเปลี่ยนคีย์ API ที่ใช้เชื่อมต่อระบบ AI');
    if (!ok) { toast('ยกเลิกการบันทึก: ไม่ได้ยืนยันการเปลี่ยนคีย์ API', 'err'); return; }
  }
  if (promptChanged) {
    const ok = await askConfirm('confirm change prompt', 'ยืนยันการเปลี่ยนพร็อมท์',
      'คุณกำลังจะเปลี่ยนพร็อมท์ที่ใช้สั่งให้ AI อ่านและดึงข้อมูลจากเอกสาร');
    if (!ok) { toast('ยกเลิกการบันทึก: ไม่ได้ยืนยันการเปลี่ยนพร็อมท์', 'err'); return; }
  }

  const cfg = { api_key: newApiKey, source_dir: newSource, output_dir: newOutput, prompt: newPrompt };
  await api.call('save_config', cfg);
  state.config = { ...state.config, ...cfg };
  if (promptChanged) await loadPromptVersions();
  refreshFolderCards();
  await refreshFileCount();
  $('saveStatus').textContent = 'บันทึกแล้ว ✓';
  setTimeout(() => { $('saveStatus').textContent = ''; }, 2500);
  toast('บันทึกการตั้งค่าเรียบร้อย', 'ok');
});

$('testBtn').addEventListener('click', async () => {
  const cleanKey = cleanApiKey($('apiKey').value);
  $('apiKey').value = cleanKey;
  
  const key = cleanKey;
  const hint = $('apiHint');
  if (!key) { hint.textContent = 'กรุณากรอกคีย์ API ก่อน'; hint.className = 'field-hint err'; return; }
  
  const keyChanged = key !== (state.config.api_key || '');
  if (keyChanged) {
    const confirmed = await askConfirm('confirm change api', 'ยืนยันการทดสอบการเชื่อมต่อ',
      'กำลังจะทดสอบการเชื่อมต่อด้วยคีย์ API ที่กรอก — กรุณาพิมพ์คำยืนยันเพื่อดำเนินการต่อ');
    if (!confirmed) { hint.textContent = 'ยกเลิกการทดสอบ'; hint.className = 'field-hint err'; return; }
  }
  
  hint.textContent = 'กำลังทดสอบการเชื่อมต่อ...'; hint.className = 'field-hint';
  const res = await api.call('test_connection', key);
  if (res.ok) {
    state.config.api_key = key; // อัปเดตเพื่อให้ตรงกับที่ backend บันทึกสำเร็จ
  }
  hint.textContent = res.message;
  hint.className = 'field-hint ' + (res.ok ? 'ok' : 'err');
});

/* ---------- Mini stats (fully realtime, driven by live results) ---------- */
function avgLabel(seconds, count) {
  if (!count || !seconds) return '-';
  const avg = seconds / count;
  return avg >= 60 ? `${Math.floor(avg / 60)} นาที ${Math.round(avg % 60)} วิ` : `${avg.toFixed(1)} วิ/ไฟล์`;
}

function updateMiniStats() {
  const ok = state.results.filter(r => r.status === 'success').length;
  const manual = state.results.filter(r => r.status === 'manual').length;
  const done = ok + manual;
  const remaining = Math.max(0, state.totalFiles - done);
  const pct = state.totalFiles ? Math.round(done / state.totalFiles * 100) : 0;
  $('mFiles').textContent = state.totalFiles ? `${remaining} จาก ${state.totalFiles} ไฟล์` : '0 ไฟล์';
  $('mOk').textContent = `${ok} ไฟล์`;
  $('mManual').textContent = `${manual} ไฟล์`;
  $('mAvg').textContent = avgLabel(state.elapsedSeconds, done);
  $('mProgress').textContent = `${pct}%`;
  $('progressPct').textContent = `${pct}%`;
  $('progressFill').style.width = `${pct}%`;
  if (state.config.source_dir) {
    $('srcHint').textContent = state.processing
      ? `กำลังประมวลผล... เหลือ ${remaining} จาก ${state.totalFiles} เอกสาร`
      : `พบ ${state.totalFiles} เอกสาร พร้อมประมวลผล`;
  }
}

/* ---------- Processing (every action asks for confirmation first) ---------- */
$('startBtn').addEventListener('click', startProcessing);
$('stopBtn').addEventListener('click', async () => {
  const ok = await askConfirm(null, 'ยืนยันการหยุดประมวลผล',
    'ระบบจะหยุดหลังจากไฟล์ปัจจุบันเสร็จ ไฟล์ที่ยังไม่ได้ประมวลผลจะคงอยู่ในโฟลเดอร์ต้นทาง และสามารถกด "เริ่มประมวลผล" เพื่อทำต่อได้ภายหลัง');
  if (!ok) return;
  api.call('stop_processing');
  toast('สั่งหยุดการประมวลผลแล้ว จะหยุดหลังจากไฟล์ปัจจุบันเสร็จ', '');
});
$('resetBtn').addEventListener('click', async () => {
  const ok = await askConfirm(null, 'ยืนยันการเริ่มใหม่',
    'ผลลัพธ์และบันทึกการทำงานบนหน้าจอจะถูกล้างทั้งหมด (ประวัติที่บันทึกไว้แล้วจะไม่หายไป)');
  if (!ok) return;
  resetProcessing();
});

async function startProcessing() {
  if (state.processing) return;
  if (!state.config.api_key) { toast('กรุณาตั้งค่าคีย์ API ก่อน', 'err'); goto('settings'); return; }
  if (!state.config.source_dir || !state.config.output_dir) { toast('กรุณาเลือกโฟลเดอร์ต้นทางและปลายทาง', 'err'); return; }
  if (!hasApi()) { toast('โหมดตัวอย่าง: เชื่อมต่อ Python เพื่อประมวลผลจริง', 'err'); return; }

  const ok = await askConfirm(null, 'ยืนยันการเริ่มประมวลผล',
    `ระบบจะเริ่มตรวจสอบและจัดเก็บเอกสาร ${state.totalFiles} ไฟล์จากโฟลเดอร์ต้นทาง ไฟล์ที่ผ่านการตรวจจะถูกย้ายไปโฟลเดอร์ปลายทาง`);
  if (!ok) return;

  resetProcessing(true);
  state.processing = true;
  state.sessionCounted = false;
  $('startBtn').disabled = true;
  $('stopBtn').disabled = false;
  $('progressLabel').textContent = 'กำลังประมวลผล...';
  await refreshFileCount();
  const res = await api.call('start_processing');
  if (res && res.error) { toast(res.error, 'err'); finishProcessing(); }
}

function resetProcessing(keepButtons) {
  state.results = [];
  state.logs = [];
  state.elapsedSeconds = 0;
  renderResults();
  renderLogs();
  updateMiniStats();
  $('mTime').textContent = '0:00';
  $('mAvg').textContent = '-';
  $('progressLabel').textContent = 'พร้อมเริ่มประมวลผล';
  $('progressPct').textContent = '0%';
  $('progressFill').style.width = '0%';
  if (!keepButtons) { $('startBtn').disabled = false; $('stopBtn').disabled = true; state.processing = false; }
}

function finishProcessing() {
  state.processing = false;
  $('startBtn').disabled = false;
  $('stopBtn').disabled = true;
  $('progressLabel').textContent = 'ประมวลผลเสร็จสิ้น';
}

/* ---------- Backend push handlers (called from Python) ---------- */
window.onResult = function (result) {
  state.results.push(result);
  renderResults();
  updateMiniStats();
  if (isPageActive('dashboard')) renderDashboardStats();
};
window.onTick = function (label) {
  $('mTime').textContent = label;
  const parts = String(label).split(':');
  state.elapsedSeconds = (Number(parts[0]) || 0) * 60 + (Number(parts[1]) || 0);
  const done = state.results.length;
  $('mAvg').textContent = avgLabel(state.elapsedSeconds, done);
};
window.onDone = async function (summary) {
  finishProcessing();
  if (summary && summary.elapsed_label) $('mTime').textContent = summary.elapsed_label;
  if (summary && summary.elapsed) state.elapsedSeconds = summary.elapsed;
  updateMiniStats();
  if (summary && summary.status === 'stopped') {
    $('progressLabel').textContent = `หยุดกลางคัน — เหลืออีก ${summary.remaining} ไฟล์`;
    toast(`หยุดกลางคัน: ประมวลผลแล้ว ${summary.total} ไฟล์ เหลือ ${summary.remaining} ไฟล์ — กด "เริ่มประมวลผล" เพื่อทำต่อ`, '');
  } else if (summary && summary.status === 'crashed') {
    $('progressLabel').textContent = `ระบบขัดข้อง — บันทึกผลที่ทำไปแล้ว ${summary.total} ไฟล์`;
    toast(`ระบบขัดข้องระหว่างประมวลผล — บันทึกผล ${summary.total} ไฟล์ที่ทำเสร็จไว้แล้ว ไฟล์ที่เหลือประมวลผลต่อได้ทันที`, 'err');
  } else {
    toast(`เสร็จสิ้น: สำเร็จ ${summary.success} • ต้องตรวจสอบ ${summary.manual}`, 'ok');
  }
  await loadDashboardBase();
  state.sessionCounted = true;
  if (isPageActive('dashboard')) renderDashboardStats();
  if (isPageActive('history')) loadHistory();
};
window.onLog = function (entry) {
  if (!entry) return;
  state.logs.push(entry);
  if (state.logs.length > MAX_LOG_ENTRIES) state.logs.shift();
  renderLogs();
};

$('clearLogBtn').addEventListener('click', () => { state.logs = []; renderLogs(); });

function renderLogs() {
  const el = $('logList');
  if (!state.logs.length) { el.innerHTML = '<p class="empty">ยังไม่มีบันทึกการทำงาน</p>'; return; }
  el.innerHTML = state.logs.map(l => `<div class="log-item ${esc(l.level || 'info')}">
    <span class="log-time">${esc(l.time || '')}</span>
    <span class="log-step">${esc(l.step || LOG_STEP_LEVEL_LABEL[l.level] || '')}</span>
    <span class="log-msg">${esc(l.message || '')}${l.hint ? `<span class="log-hint">💡 วิธีแก้ไข: ${esc(l.hint)}</span>` : ''}</span>
  </div>`).join('');
  el.scrollTop = el.scrollHeight;
}

/* ---------- Results table ---------- */
$('resultSearch').addEventListener('input', (e) => {
  state.search = e.target.value.toLowerCase();
  state.currentPage = 1;
  renderResults();
});

document.querySelectorAll('.filter-tabs .tab[data-filter]').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.filter-tabs .tab[data-filter]').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    state.filter = tab.dataset.filter;
    state.currentPage = 1;
    renderResults();
  });
});

const sizeSelectEl = $('pageSizeSelect');
if (sizeSelectEl) {
  sizeSelectEl.addEventListener('change', (e) => {
    state.pageSize = Number(e.target.value) || 10;
    state.currentPage = 1;
    renderResults();
  });
}

function renderResults() {
  const body = $('resultBody');
  let rows = state.results;
  if (state.filter !== 'all') rows = rows.filter(r => r.status === state.filter);
  if (state.search) rows = rows.filter(r => (r.filename + ' ' + r.name).toLowerCase().includes(state.search));

  const totalFiltered = rows.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / state.pageSize));

  if (state.currentPage > totalPages) state.currentPage = totalPages;
  if (state.currentPage < 1) state.currentPage = 1;

  const startIdx = totalFiltered > 0 ? (state.currentPage - 1) * state.pageSize : 0;
  const endIdx = Math.min(startIdx + state.pageSize, totalFiltered);
  const pageRows = rows.slice(startIdx, endIdx);

  if (totalFiltered > 0) {
    $('resultCount').textContent = `แสดง ${startIdx + 1}-${endIdx} จาก ${totalFiltered} รายการ` + (state.results.length !== totalFiltered ? ` (ทั้งหมด ${state.results.length} รายการ)` : '');
  } else {
    $('resultCount').textContent = `แสดง 0 จาก ${state.results.length} รายการ`;
  }

  if (!pageRows.length) {
    body.innerHTML = `<tr><td colspan="12" class="empty">${state.results.length ? 'ไม่พบรายการที่ค้นหา' : 'ยังไม่มีรายการ กด "เริ่มประมวลผล" เพื่อเริ่มตรวจสอบเอกสาร'}</td></tr>`;
  } else {
    body.innerHTML = pageRows.map(r => {
      const status = r.status === 'success'
        ? '<span class="status-pill success">สำเร็จ</span>'
        : `<span class="status-pill manual" title="${esc(r.reason || '')}">ต้องตรวจสอบ</span>`;
      const sign = r.signed ? '<span class="sign-yes">✓ มี</span>' : '<span class="sign-no">✕ ไม่มี</span>';
      return `<tr class="clickable-row" data-relpath="${esc(r.rel_path || '')}" title="คลิกเพื่อเปิด/ตรวจสอบไฟล์ในเครื่อง">
        <td>${r.index}</td>
        <td>${esc(r.filename)}</td>
        <td>${esc(r.name)}</td>
        <td>${esc(r.id_card)}</td>
        <td>${esc(r.loan_type)}</td>
        <td>${sign}</td>
        <td class="num-cell">${money(r.tuition_fee)}</td>
        <td class="num-cell">${money(r.living_allowance_monthly)}</td>
        <td class="num-cell">${r.living_allowance_months == null ? '-' : esc(r.living_allowance_months)}</td>
        <td class="num-cell">${money(r.living_allowance_total)}</td>
        <td class="num-cell">${money(r.net_total)}</td>
        <td>${status}</td>
      </tr>`;
    }).join('');

    body.querySelectorAll('.clickable-row').forEach(tr => {
      tr.addEventListener('click', () => {
        const path = tr.dataset.relpath;
        if (path) {
          api.call('reveal_file_or_folder', path).then(res => {
            if (res && !res.ok) toast(res.message, 'err');
          });
        }
      });
    });
  }

  renderPagination(totalFiltered, totalPages, startIdx, endIdx);
}

function renderPagination(totalFiltered, totalPages, startIdx, endIdx) {
  const paginationEl = $('resultPagination');
  const infoEl = $('paginationInfo');
  const buttonsEl = $('paginationButtons');
  if (!paginationEl || !infoEl || !buttonsEl) return;

  if (totalFiltered === 0) {
    infoEl.innerHTML = 'ยังไม่มีรายการที่จะแสดง';
    buttonsEl.innerHTML = '';
    return;
  }

  infoEl.innerHTML = `<span class="page-info-highlight">แสดงรายการที่ ${startIdx + 1} - ${endIdx}</span> จากทั้งหมด <b>${totalFiltered.toLocaleString('th-TH')}</b> รายการ <span class="page-total-badge">หน้า ${state.currentPage} / ${totalPages}</span>`;

  let html = '';

  // First & Prev buttons
  html += `<button class="page-btn" ${state.currentPage === 1 ? 'disabled' : ''} onclick="goToPage(1)" title="หน้าแรก">«</button>`;
  html += `<button class="page-btn" ${state.currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${state.currentPage - 1})" title="ก่อนหน้า">‹ ก่อนหน้า</button>`;

  // Page numbers with smart ellipsis
  const pages = getPaginationPages(state.currentPage, totalPages);
  pages.forEach(p => {
    if (p === '...') {
      html += `<span class="page-btn ellipsis">...</span>`;
    } else {
      const activeClass = p === state.currentPage ? 'active' : '';
      html += `<button class="page-btn ${activeClass}" onclick="goToPage(${p})">${p}</button>`;
    }
  });

  // Next & Last buttons
  html += `<button class="page-btn" ${state.currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${state.currentPage + 1})" title="หน้าถัดไป">ถัดไป ›</button>`;
  html += `<button class="page-btn" ${state.currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${totalPages})" title="หน้าสุดท้าย">»</button>`;

  buttonsEl.innerHTML = html;
}

function goToPage(page) {
  if (page < 1) return;
  state.currentPage = page;
  renderResults();
}
window.goToPage = goToPage;

function getPaginationPages(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages = [];
  if (current <= 4) {
    for (let i = 1; i <= 5; i++) pages.push(i);
    pages.push('...');
    pages.push(total);
  } else if (current >= total - 3) {
    pages.push(1);
    pages.push('...');
    for (let i = total - 4; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    pages.push('...');
    for (let i = current - 1; i <= current + 1; i++) pages.push(i);
    pages.push('...');
    pages.push(total);
  }
  return pages;
}

/* Format a numeric amount as Thai baht with thousands separators, or '-' if missing. */
function money(v) {
  if (v == null || v === '' || isNaN(Number(v))) return '-';
  return Number(v).toLocaleString('th-TH', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

/* ---------- Dashboard ---------- */
const TH_MONTHS_JS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];

function dayKeyOf(entry) {
  // Prefer the machine timestamp; fall back to the Thai date label.
  if (entry.timestamp) return String(entry.timestamp).slice(0, 10); // YYYY-MM-DD
  const parts = (entry.date || '').split(' ');
  return parts.length >= 3 ? `${parts[2]}-${parts[1]}-${parts[0]}` : (entry.date || '');
}

function dayLabelOf(entry) {
  if (entry.timestamp) {
    const d = new Date(entry.timestamp);
    if (!isNaN(d)) return `${String(d.getDate()).padStart(2, '0')} ${TH_MONTHS_JS[d.getMonth()]}`;
  }
  const parts = (entry.date || '').split(' ');
  return parts.length >= 2 ? `${parts[0]} ${parts[1]}` : (entry.date || '');
}

function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function rangeStart(range) {
  const d = new Date(); d.setHours(0, 0, 0, 0);
  if (range === 'today') return d;
  if (range === '7d') { d.setDate(d.getDate() - 6); return d; }
  if (range === '30d') { d.setDate(d.getDate() - 29); return d; }
  return null; // all
}

function filteredHistory() {
  const rows = state.history || [];
  const start = rangeStart(state.dashRange);
  if (!start) return rows;
  return rows.filter(r => {
    if (!r.timestamp) return false;
    const d = new Date(r.timestamp);
    return !isNaN(d) && d >= start;
  });
}

async function loadDashboardBase() {
  state.history = await api.call('get_history') || [];
}

async function loadDashboard() {
  if (!state.history) await loadDashboardBase();
  renderDashboardStats();
}

/* Range filter dropdown select */
const rangeSelectEl = $('dashRangeSelect');
if (rangeSelectEl) {
  rangeSelectEl.value = state.dashRange || '7d';
  rangeSelectEl.addEventListener('change', (e) => {
    state.dashRange = e.target.value;
    state.dashSelectedBar = null; // reset bar selection when the range changes
    renderDashboardStats();
  });
}

$('dashClearSel').addEventListener('click', () => {
  state.dashSelectedBar = null;
  renderDashboardStats();
});

function renderDashboardStats() {
  const rows = filteredHistory();
  // Aggregate runs into one group per calendar day (item 9).
  const dayMap = new Map();
  rows.forEach(r => {
    const key = dayKeyOf(r);
    if (!dayMap.has(key)) dayMap.set(key, { key, label: dayLabelOf(r), total: 0, success: 0, manual: 0, runs: [] });
    const g = dayMap.get(key);
    g.total += r.total || 0;
    g.success += r.success || 0;
    g.manual += r.manual || 0;
    g.runs.push(r);
  });
  const days = [...dayMap.values()].sort((a, b) => a.key.localeCompare(b.key));
  const chartDays = days.slice(-14); // keep the chart readable

  // Drop selection if it fell outside the current range.
  if (state.dashSelectedBar && !dayMap.has(state.dashSelectedBar.day)) state.dashSelectedBar = null;
  const selected = state.dashSelectedBar ? dayMap.get(state.dashSelectedBar.day) : null;

  // Stats reflect either the selected bar (item 10) or the whole filtered range.
  const statRows = selected ? selected.runs : rows;
  let total = statRows.reduce((s, r) => s + (r.total || 0), 0);
  let success = statRows.reduce((s, r) => s + (r.success || 0), 0);
  let manual = statRows.reduce((s, r) => s + (r.manual || 0), 0);

  // Live (in-progress) results count toward "today".
  const liveOk = state.sessionCounted ? 0 : state.results.filter(r => r.status === 'success').length;
  const liveManual = state.sessionCounted ? 0 : state.results.filter(r => r.status === 'manual').length;
  const liveVisible = (liveOk + liveManual) > 0 && (!state.dashSelectedBar || state.dashSelectedBar.day === todayKey());
  if (liveVisible) { total += liveOk + liveManual; success += liveOk; manual += liveManual; }

  const rate = total ? Math.round(success / total * 100) : 0;
  $('dashTotal').textContent = total;
  $('dashSuccess').textContent = success;
  $('dashManual').textContent = manual;
  $('dashRate').textContent = `${rate}%`;

  // Selection helper UI
  const clearBtn = $('dashClearSel');
  if (selected && state.dashSelectedBar) {
    const isAll = state.dashSelectedBar.type === 'all';
    clearBtn.hidden = false;
    $('dashSelLabel').textContent = isAll ? selected.label : `${selected.label} — ${BAR_TYPE_LABELS[state.dashSelectedBar.type]}`;
    $('chartSub').textContent = isAll
      ? `กำลังแสดงข้อมูลเฉพาะวันที่ ${selected.label} • คลิกแท่งแต่ละแท่งเพื่อดูเฉพาะประเภท`
      : `กำลังแสดงข้อมูล "${BAR_TYPE_LABELS[state.dashSelectedBar.type]}" ของวันที่ ${selected.label} • คลิกแท่งเดิมอีกครั้งเพื่อยกเลิก`;
  } else {
    clearBtn.hidden = true;
    $('dashSelLabel').textContent = '';
    $('chartSub').textContent = 'รวมข้อมูลรายวัน • คลิกที่แท่งกราฟแต่ละแท่งเพื่อดูข้อมูลเฉพาะ';
  }

  renderChart(chartDays);

  // Recent runs table follows the same selection/filter.
  const recent = statRows.slice(0, 5).map(r => ({ ...r }));
  if (liveVisible || state.processing) {
    recent.unshift({
      date: state.processing ? 'กำลังประมวลผล…' : 'รอบล่าสุด',
      total: liveOk + liveManual, success: liveOk, manual: liveManual, live: state.processing,
    });
  }
  renderRecent(recent.slice(0, 5));
}

const BAR_TYPE_LABELS = { total: 'ทั้งหมด', success: 'สำเร็จ', manual: 'ต้องตรวจสอบ', all: 'ทั้งชุด' };

function renderChart(days) {
  const el = $('dashChart');
  if (!days.length) { el.innerHTML = '<p class="muted" style="margin:auto">ยังไม่มีข้อมูลกราฟในช่วงเวลาที่เลือก</p>'; return; }
  const max = Math.max(1, ...days.map(c => c.total));
  const curSel = state.dashSelectedBar;
  el.innerHTML = days.map(c => {
    const th = Math.round(c.total / max * 140);
    const oh = Math.round(c.success / max * 140);
    const mh = Math.round(c.manual / max * 140);
    const isThisDay = curSel && curSel.day === c.key;
    const groupCls = curSel ? (isThisDay ? ' has-sel' : ' dim') : '';
    const bCls = (type) => {
      if (!curSel) return '';
      return (isThisDay && (curSel.type === 'all' || curSel.type === type)) ? ' bar-selected' : ' bar-dim';
    };
    return `<div class="bar-group clickable${groupCls}">
      <span class="bval">${c.total}</span>
      <div class="bars">
        <div class="bar total${bCls('total')}" data-day="${esc(c.key)}" data-type="total" style="height:${th}px" title="${esc(c.label)} — ทั้งหมด ${c.total}"></div>
        <div class="bar ok${bCls('success')}" data-day="${esc(c.key)}" data-type="success" style="height:${oh}px" title="${esc(c.label)} — สำเร็จ ${c.success}"></div>
        <div class="bar manual${bCls('manual')}" data-day="${esc(c.key)}" data-type="manual" style="height:${mh}px" title="${esc(c.label)} — ต้องตรวจสอบ ${c.manual}"></div>
      </div>
      <span class="blabel">${esc(c.label)}</span>
    </div>`;
  }).join('');
  el.querySelectorAll('.bar[data-day]').forEach(bar => {
    bar.addEventListener('click', (e) => {
      e.stopPropagation();
      const day = bar.dataset.day;
      const type = bar.dataset.type;
      state.dashSelectedBar = (curSel && curSel.day === day && curSel.type === type) ? null : { day, type };
      renderDashboardStats();
    });
  });
  // Click on the label / value area (outside the bars) selects the entire day
  el.querySelectorAll('.bar-group.clickable').forEach(g => {
    g.addEventListener('click', () => {
      const bar0 = g.querySelector('.bar[data-day]');
      if (!bar0) return;
      const day = bar0.dataset.day;
      state.dashSelectedBar = (curSel && curSel.day === day && curSel.type === 'all') ? null : { day, type: 'all' };
      renderDashboardStats();
    });
  });
}

function statusPill(r) {
  if (r.live) return '<span class="status-pill live">● กำลังประมวลผล</span>';
  if (r.status === 'stopped') return `<span class="status-pill stopped" title="เหลือ ${r.remaining || 0} ไฟล์">หยุดกลางคัน</span>`;
  if (r.status === 'crashed') return `<span class="status-pill crashed" title="เหลือ ${r.remaining || 0} ไฟล์">ขัดข้อง</span>`;
  return '<span class="status-pill success">เสร็จสิ้น</span>';
}

function renderRecent(recent) {
  const body = $('dashRecent');
  if (!recent.length) { body.innerHTML = '<tr><td colspan="5" class="empty">ยังไม่มีข้อมูล</td></tr>'; return; }
  body.innerHTML = recent.map(r => `<tr>
    <td>${esc(r.date)}</td>
    <td>${r.total}</td>
    <td class="num-ok">${r.success}</td>
    <td class="num-manual">${r.manual}</td>
    <td style="text-align:right">${statusPill(r)}</td>
  </tr>`).join('');
}

/* ---------- History ---------- */
/* Average processing time per document for a run (item 3). */
function runAvgLabel(r) {
  let seconds = r.elapsed;
  if (seconds == null && r.elapsed_label) {
    const p = String(r.elapsed_label).split(':');
    seconds = (Number(p[0]) || 0) * 60 + (Number(p[1]) || 0);
  }
  if (!seconds || !r.total) return '-';
  return avgLabel(seconds, r.total);
}

async function loadHistory() {
  const rows = await api.call('get_history');
  const body = $('historyBody');
  if (!rows.length) { body.innerHTML = '<tr><td colspan="8" class="empty">ยังไม่มีประวัติการประมวลผล</td></tr>'; return; }
  body.innerHTML = rows.map(r => `<tr>
    <td>${esc(r.date)}</td>
    <td>${esc(r.finished || '-')}</td>
    <td>${r.total}</td>
    <td class="num-ok">${r.success}</td>
    <td class="num-manual">${r.manual}</td>
    <td><span class="time-cell">🕒 ${esc(r.elapsed_label || '-')}</span></td>
    <td><span class="time-cell">${esc(runAvgLabel(r))}</span></td>
    <td>${statusPill(r)}</td>
  </tr>`).join('');
}

/* ---------- Prompt versions (item 8) ---------- */
async function loadPromptVersions() {
  state.promptVersions = await api.call('get_prompt_versions') || [];
  const sel = $('promptVersionSelect');
  const current = (state.config.prompt || '').trim();
  sel.innerHTML = '<option value="">เวอร์ชันปัจจุบัน (ที่ใช้งานอยู่)</option>' +
    state.promptVersions.map(v => {
      const isCurrent = (v.prompt || '').trim() === current;
      return `<option value="${esc(v.filename)}">${esc(v.filename)}${isCurrent ? ' (ใช้งานอยู่)' : ''}</option>`;
    }).join('');
}

$('promptVersionSelect').addEventListener('change', (e) => {
  const val = e.target.value;
  if (!val) { $('promptText').value = state.config.prompt || ''; return; }
  const v = state.promptVersions.find(x => x.filename === val);
  if (!v) return;
  $('promptText').value = v.prompt || '';
  toast(`โหลดพร็อมท์จากไฟล์ ${v.filename} แล้ว — กด "บันทึกพร็อมท์" เพื่อกลับไปใช้เวอร์ชันนี้`, '');
});

/* ---------- Utils ---------- */
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

/* ---------- Clickable Cards setup ---------- */
function initClickableCards() {
  const dashCard = $('dashManualCard');
  if (dashCard) {
    dashCard.addEventListener('click', () => {
      api.call('reveal_file_or_folder', 'Manual').then(res => {
        if (res && !res.ok) toast(res.message, 'err');
      });
    });
  }
  const procCard = $('processManualCard');
  if (procCard) {
    procCard.addEventListener('click', () => {
      api.call('reveal_file_or_folder', 'Manual').then(res => {
        if (res && !res.ok) toast(res.message, 'err');
      });
    });
  }
}

/* ---------- Boot ---------- */
function boot() { loadConfig().then(loadPromptVersions); loadDashboardBase(); initClickableCards(); goto('dashboard'); }
if (hasApi()) { boot(); }
else { window.addEventListener('pywebviewready', boot); setTimeout(() => { if (!window.__booted) { window.__booted = true; boot(); } }, 400); }
window.addEventListener('pywebviewready', () => { if (!window.__booted) { window.__booted = true; boot(); } });
