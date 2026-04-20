document.addEventListener('DOMContentLoaded', () => {
  if (!API.requireAuth()) return;

  let allTemplates = [];
  let currentFilter = 'all';

  const grid = document.getElementById('templates-grid');
  const emptyState = document.getElementById('empty-state');
  const filterBtns = document.querySelectorAll('[data-marketplace]');

  async function loadTemplates() {
    try {
      allTemplates = await API.getJSON('/api/templates/?limit=100');
      renderTemplates();
    } catch (e) {
      console.error('Failed to load templates', e);
    }
  }

  function renderTemplates() {
    const filtered = currentFilter === 'all'
      ? allTemplates
      : allTemplates.filter(t => t.marketplace === currentFilter);

    if (filtered.length === 0) {
      grid.innerHTML = '';
      emptyState.style.display = 'block';
      return;
    }
    emptyState.style.display = 'none';

    grid.innerHTML = filtered.map(t => `
      <div class="template-card card" data-uid="${t.uid}">
        <button class="btn-delete-overlay" onclick="deleteTemplate('${t.uid}')" title="Удалить шаблон">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        </button>
        <div class="template-preview">
          ${t.preview_url
            ? `<img src="${t.preview_url}" alt="${t.name}" loading="lazy">`
            : `<div class="preview-placeholder">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>
                </svg>
                <span>${t.canvas_width}×${t.canvas_height}</span>
               </div>`
          }
        </div>
        <div class="template-info">
          <h3 class="template-name">${escapeHtml(t.name)}</h3>
          <span class="marketplace-badge marketplace-${t.marketplace}">${marketplaceLabel(t.marketplace)}</span>
        </div>
        <div class="template-actions">
          <a href="/editor/${t.uid}" class="btn btn-primary btn-sm">Редактировать</a>
          <a href="/generate/${t.uid}" class="btn btn-secondary btn-sm">Генерировать</a>
        </div>
      </div>
    `).join('');
  }

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.marketplace;
      renderTemplates();
    });
  });

  window.deleteTemplate = async (uid) => {
    if (!confirm('Удалить шаблон? Это действие нельзя отменить.')) return;
    try {
      await API.delete(`/api/templates/${uid}`);
      allTemplates = allTemplates.filter(t => t.uid !== uid);
      renderTemplates();
    } catch (e) {
      alert('Не удалось удалить шаблон');
    }
  };

  function marketplaceLabel(m) {
    const labels = { wb: 'Wildberries', ozon: 'Ozon', universal: 'Универсальный' };
    return labels[m] || m;
  }

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  loadTemplates();
});
