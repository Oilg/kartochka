let batchUid = null;
let pollInterval = null;
let currentFilter = null;
let currentPage = 1;
const PAGE_SIZE = 20;

async function initBatchPage(uid) {
  batchUid = uid;
  await loadBatch();
  await loadItems(null, 1);
}

async function loadBatch() {
  try {
    const batch = await API.getJSON(`/api/catalog/batches/${batchUid}`);
    renderBatch(batch);

    const activeStatuses = ['pending', 'processing'];
    if (activeStatuses.includes(batch.status)) {
      startPolling();
    } else {
      stopPolling();
    }

    // Update publish progress if applicable
    if (batch.publish_status) {
      renderPublishStatus(batch);
    }
  } catch(e) {
    document.getElementById('batch-title').textContent = 'Ошибка загрузки';
  }
}

function renderBatch(batch) {
  document.getElementById('batch-title').textContent = batch.name;

  const statusMap = {
    pending: ['В очереди', 'secondary'],
    processing: ['Генерация', 'warning'],
    completed: ['Готово', 'success'],
    completed_with_errors: ['С ошибками', 'warning'],
    failed: ['Ошибка', 'danger'],
  };
  const [label, cls] = statusMap[batch.status] || [batch.status, 'secondary'];
  const badge = document.getElementById('batch-status-badge');
  badge.textContent = label;
  badge.className = `status-badge status-${cls}`;

  document.getElementById('progress-bar').style.width = batch.percentage + '%';
  document.getElementById('progress-text').textContent = `${batch.percentage}%`;
  document.getElementById('stat-total').textContent = batch.total_items;
  document.getElementById('stat-done').textContent = batch.processed_items;
  document.getElementById('stat-failed').textContent = batch.failed_items;

  // Buttons
  if (batch.zip_path) {
    const dlBtn = document.getElementById('download-btn');
    dlBtn.href = `/api/catalog/batches/${batchUid}/download`;
    dlBtn.style.display = 'inline-block';
  }
  if (['completed', 'completed_with_errors'].includes(batch.status)) {
    document.getElementById('publish-btn').style.display = 'inline-block';
  }
  if (batch.failed_items > 0) {
    document.getElementById('retry-btn').style.display = 'inline-block';
  }
}

function renderPublishStatus(batch) {
  const section = document.getElementById('publish-progress');
  const statusText = document.getElementById('publish-status-text');
  const statsText = document.getElementById('publish-stats');

  const statusMap = {
    publishing: 'Публикация...',
    published: 'Опубликовано ✓',
    publish_failed: 'Ошибка публикации',
  };
  statusText.textContent = statusMap[batch.publish_status] || batch.publish_status;
  statsText.textContent = `${batch.published_items} опубликовано, ${batch.publish_failed_items} ошибок`;
  section.style.display = 'block';
}

function startPolling() {
  if (pollInterval) return;
  pollInterval = setInterval(async () => {
    try {
      const batch = await API.getJSON(`/api/catalog/batches/${batchUid}`);
      renderBatch(batch);
      if (!['pending', 'processing'].includes(batch.status)) {
        stopPolling();
        await loadItems(currentFilter, currentPage);
      }
    } catch(e) {}
  }, 2000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function loadItems(filter, page) {
  currentFilter = filter;
  currentPage = page;
  document.getElementById('gallery').innerHTML = '';
  document.getElementById('gallery-loading').style.display = 'block';
  document.getElementById('gallery-empty').style.display = 'none';

  try {
    const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
    if (filter) params.set('status', filter);
    const data = await API.getJSON(`/api/catalog/batches/${batchUid}/items?${params}`);

    document.getElementById('gallery-loading').style.display = 'none';

    if (data.items.length === 0) {
      document.getElementById('gallery-empty').style.display = 'block';
      return;
    }

    const gallery = document.getElementById('gallery');
    gallery.innerHTML = data.items.map(item => {
      const imgSrc = item.output_path
        ? `/storage/generated/${item.output_path.split('/').pop()}`
        : (item.image_url || '');
      const statusColor = item.generation_status === 'completed' ? 'var(--success)'
        : item.generation_status === 'failed' ? 'var(--danger)' : 'var(--secondary)';
      return `<div style="background:var(--white); border:1px solid var(--border); border-radius:8px; overflow:hidden; cursor:pointer;" onclick="openItem(${JSON.stringify(item).replace(/"/g, '&quot;')})">
        ${imgSrc ? `<img src="${imgSrc}" alt="" style="width:100%; aspect-ratio:1; object-fit:contain;" onerror="this.style.display='none'">` : '<div style="width:100%; aspect-ratio:1; background:var(--border); display:flex; align-items:center; justify-content:center; color:var(--secondary);">Нет фото</div>'}
        <div style="padding:8px;">
          <div style="font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${item.title || '—'}</div>
          <div style="font-size:11px; color:${statusColor};">${item.generation_status}</div>
        </div>
      </div>`;
    }).join('');

    // Pagination
    const totalPages = Math.ceil(data.total / PAGE_SIZE);
    const pag = document.getElementById('gallery-pagination');
    pag.innerHTML = '';
    for (let p = 1; p <= Math.min(totalPages, 10); p++) {
      const btn = document.createElement('button');
      btn.className = `btn btn-sm ${p === page ? 'btn-primary' : 'btn-secondary'}`;
      btn.textContent = p;
      btn.onclick = () => loadItems(filter, p);
      pag.appendChild(btn);
    }
  } catch(e) {
    document.getElementById('gallery-loading').textContent = 'Ошибка загрузки';
  }
}

function filterItems(status) {
  ['all', 'done', 'failed', 'pending'].forEach(t => {
    document.getElementById(`item-tab-${t}`).classList.toggle('active', t === (status || 'all'));
  });
  // Map tab names
  const filterMap = { done: 'completed', all: null };
  loadItems(filterMap[status] !== undefined ? filterMap[status] : status, 1);
}

function openItem(item) {
  document.getElementById('modal-title').textContent = item.title || 'Карточка';
  const imgSrc = item.output_path
    ? `/storage/generated/${item.output_path.split('/').pop()}`
    : (item.image_url || '');
  const img = document.getElementById('modal-img');
  img.src = imgSrc;
  img.style.display = imgSrc ? 'block' : 'none';

  document.getElementById('modal-info').innerHTML = `
    <table style="width:100%; font-size:13px;">
      ${item.external_id ? `<tr><td style="color:var(--secondary); padding:4px 0;">Артикул</td><td>${item.external_id}</td></tr>` : ''}
      ${item.brand ? `<tr><td style="color:var(--secondary); padding:4px 0;">Бренд</td><td>${item.brand}</td></tr>` : ''}
      ${item.price ? `<tr><td style="color:var(--secondary); padding:4px 0;">Цена</td><td>${item.price}</td></tr>` : ''}
      <tr><td style="color:var(--secondary); padding:4px 0;">Статус</td><td>${item.generation_status}</td></tr>
    </table>
  `;
  document.getElementById('item-modal').style.display = 'flex';
}

function closeItemModal() {
  document.getElementById('item-modal').style.display = 'none';
}

function openPublishModal() {
  document.getElementById('publish-modal').style.display = 'flex';
}

function closePublishModal() {
  document.getElementById('publish-modal').style.display = 'none';
}

async function publishBatch() {
  const marketplace = document.getElementById('publish-marketplace').value;
  closePublishModal();
  const formData = new FormData();
  formData.append('marketplace', marketplace);
  try {
    const r = await fetch(`/api/catalog/batches/${batchUid}/publish-to-marketplace`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${API.getToken()}` },
      body: formData,
    });
    if (!r.ok) { const e = await r.json(); alert(e.detail || 'Ошибка'); return; }
    document.getElementById('publish-progress').style.display = 'block';
    document.getElementById('publish-status-text').textContent = 'Публикация запущена...';
    // Poll publish status
    const pollPub = setInterval(async () => {
      try {
        const status = await API.getJSON(`/api/catalog/batches/${batchUid}/publish-status`);
        renderPublishStatus({ ...status, publish_status: status.publish_status });
        if (!['publishing'].includes(status.publish_status)) clearInterval(pollPub);
      } catch(e) {}
    }, 3000);
  } catch(e) {
    alert('Ошибка запуска публикации');
  }
}

async function retryFailed() {
  try {
    const data = await API.postJSON(`/api/catalog/batches/${batchUid}/retry-failed`, {});
    alert(`Повторный запуск для ${data.retried} элементов`);
    await loadBatch();
  } catch(e) {
    alert('Ошибка');
  }
}

// Close modals on outside click
document.addEventListener('click', e => {
  if (e.target === document.getElementById('item-modal')) closeItemModal();
  if (e.target === document.getElementById('publish-modal')) closePublishModal();
});
