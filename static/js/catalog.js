let selectedFile = null;
let detectedColumns = [];
let suggestedMapping = {};
const KARTOCHKA_FIELDS = ['title', 'price', 'old_price', 'discount', 'brand', 'image_url', 'external_id'];

async function initCatalogUpload() {
  // Check plan
  try {
    const user = await API.getJSON('/api/auth/me');
    if (user.plan !== 'pro') {
      document.getElementById('upgrade-overlay').style.display = 'flex';
    }
  } catch(e) {}

  // Load templates for selects
  try {
    const templates = await API.getJSON('/api/templates/');
    ['csv-template', 'wb-template', 'ozon-template'].forEach(id => {
      const sel = document.getElementById(id);
      if (!sel) return;
      sel.innerHTML = '<option value="">-- выберите шаблон --</option>' +
        templates.map(t => `<option value="${t.uid}">${t.name}</option>`).join('');
    });
  } catch(e) {}

  // Load marketplace connection statuses
  try {
    const creds = await API.getJSON('/api/marketplace-credentials/');
    const wbCred = creds.find(c => c.marketplace === 'wildberries');
    const ozonCred = creds.find(c => c.marketplace === 'ozon');
    document.getElementById('wb-connect-status').innerHTML = wbCred && wbCred.is_valid
      ? '<div style="color:var(--success);">✓ Wildberries подключён</div>'
      : '<div style="color:var(--danger);">✗ Wildberries не подключён. <a href="/marketplace/connect">Подключить</a></div>';
    document.getElementById('ozon-connect-status').innerHTML = ozonCred && ozonCred.is_valid
      ? '<div style="color:var(--success);">✓ Ozon подключён</div>'
      : '<div style="color:var(--danger);">✗ Ozon не подключён. <a href="/marketplace/connect">Подключить</a></div>';
  } catch(e) {}

  setupDropZone();
}

function setupDropZone() {
  const zone = document.getElementById('drop-zone');
  if (!zone) return;

  zone.addEventListener('click', () => document.getElementById('catalog-file').click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--accent)'; });
  zone.addEventListener('dragleave', () => { zone.style.borderColor = 'var(--border)'; });
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.style.borderColor = 'var(--border)';
    const f = e.dataTransfer.files[0];
    if (f) handleFileSelect(f);
  });
}

async function handleFileSelect(file) {
  if (!file) return;
  selectedFile = file;
  document.getElementById('file-info').style.display = 'flex';
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('step2').style.display = 'block';

  // Auto-detect columns
  const formData = new FormData();
  formData.append('file', file);
  try {
    const r = await fetch('/api/catalog/detect-columns', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${API.getToken()}` },
      body: formData,
    });
    const data = await r.json();
    detectedColumns = data.columns || [];
    suggestedMapping = data.suggested_mapping || {};
    renderMappingTable(detectedColumns, suggestedMapping);
    document.getElementById('step3').style.display = 'block';
  } catch(e) {
    document.getElementById('mapping-tbody').innerHTML = '<tr><td colspan="2" style="color:var(--danger);">Ошибка чтения файла</td></tr>';
  }
}

function renderMappingTable(columns, suggested) {
  const tbody = document.getElementById('mapping-tbody');
  const options = '<option value="">-- не использовать --</option>' +
    KARTOCHKA_FIELDS.map(f => `<option value="${f}">${f}</option>`).join('');

  tbody.innerHTML = columns.map(col => {
    const suggested_val = suggested[col] || '';
    const opts = KARTOCHKA_FIELDS.map(f =>
      `<option value="${f}" ${f === suggested_val ? 'selected' : ''}>${f}</option>`
    ).join('');
    return `<tr>
      <td style="font-family:monospace;">${col}</td>
      <td><select class="form-control col-map" data-col="${col}">
        <option value="">-- не использовать --</option>${opts}
      </select></td>
    </tr>`;
  }).join('');
}

function autoMap() {
  const selects = document.querySelectorAll('.col-map');
  selects.forEach(sel => {
    const col = sel.dataset.col;
    const mapped = suggestedMapping[col];
    if (mapped) sel.value = mapped;
  });
}

function clearFile() {
  selectedFile = null;
  document.getElementById('file-info').style.display = 'none';
  document.getElementById('catalog-file').value = '';
  document.getElementById('step2').style.display = 'none';
  document.getElementById('step3').style.display = 'none';
}

function getColumnMapping() {
  const mapping = {};
  document.querySelectorAll('.col-map').forEach(sel => {
    if (sel.value) mapping[sel.dataset.col] = sel.value;
  });
  return mapping;
}

async function submitCsvBatch() {
  if (!selectedFile) { alert('Выберите файл'); return; }
  const templateUid = document.getElementById('csv-template').value;
  if (!templateUid) { alert('Выберите шаблон'); return; }

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = 'Запуск...';

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('template_uid', templateUid);
  formData.append('marketplace', document.getElementById('csv-marketplace').value);
  formData.append('output_format', document.getElementById('csv-format').value);
  formData.append('batch_name', document.getElementById('csv-batch-name').value || selectedFile.name);
  formData.append('column_mapping', JSON.stringify(getColumnMapping()));

  try {
    const r = await fetch('/api/catalog/upload', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${API.getToken()}` },
      body: formData,
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Ошибка'); }
    const batch = await r.json();
    window.location = `/catalog/batches/${batch.uid}`;
  } catch(e) {
    alert('Ошибка: ' + e.message);
    btn.disabled = false;
    btn.textContent = '🚀 Начать генерацию';
  }
}

async function importFromMarketplace(marketplace) {
  const prefix = marketplace === 'wildberries' ? 'wb' : 'ozon';
  const templateUid = document.getElementById(`${prefix}-template`).value;
  if (!templateUid) { alert('Выберите шаблон'); return; }

  const formData = new FormData();
  formData.append('marketplace', marketplace);
  formData.append('template_uid', templateUid);
  formData.append('output_format', document.getElementById(`${prefix}-format`).value);
  formData.append('batch_name', document.getElementById(`${prefix}-batch-name`).value);

  try {
    const r = await fetch('/api/catalog/import-from-marketplace', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${API.getToken()}` },
      body: formData,
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Ошибка'); }
    const batch = await r.json();
    window.location = `/catalog/batches/${batch.uid}`;
  } catch(e) {
    alert('Ошибка: ' + e.message);
  }
}

function switchTab(tab) {
  ['csv', 'wb', 'ozon'].forEach(t => {
    document.getElementById(`tab-${t}`).classList.toggle('active', t === tab);
    document.getElementById(`pane-${t}`).style.display = t === tab ? 'block' : 'none';
  });
}
