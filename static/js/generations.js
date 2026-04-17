document.addEventListener('DOMContentLoaded', () => {
  // Generation result page - poll for status
  const genUid = document.getElementById('generation-uid')?.value;
  if (genUid) {
    startPolling(genUid);
    return;
  }

  // Generation new page
  const form = document.getElementById('generation-form');
  if (form) initGenerationForm();
});

async function startPolling(uid) {
  const spinner = document.getElementById('status-spinner');
  const statusText = document.getElementById('status-text');
  const resultSection = document.getElementById('result-section');
  const errorSection = document.getElementById('error-section');

  async function poll() {
    try {
      const data = await API.getJSON(`/api/generations/${uid}`);
      if (statusText) statusText.textContent = statusLabel(data.status);

      if (data.status === 'completed') {
        if (spinner) spinner.style.display = 'none';
        if (resultSection) {
          resultSection.style.display = 'block';
          const img = document.getElementById('result-image');
          if (img) img.src = `/api/generations/${uid}/download`;
          const dlBtn = document.getElementById('download-btn');
          if (dlBtn) dlBtn.href = `/api/generations/${uid}/download`;
        }
        return;
      }

      if (data.status === 'failed') {
        if (spinner) spinner.style.display = 'none';
        if (errorSection) {
          errorSection.style.display = 'block';
          const errMsg = document.getElementById('error-message');
          if (errMsg) errMsg.textContent = data.error_message || 'Неизвестная ошибка';
        }
        return;
      }

      // Still pending/processing - poll again
      setTimeout(poll, 2000);
    } catch (e) {
      console.error('Polling error', e);
      setTimeout(poll, 3000);
    }
  }

  poll();
}

function statusLabel(status) {
  const labels = {
    pending: 'В очереди...',
    processing: 'Генерация...',
    completed: 'Готово!',
    failed: 'Ошибка',
  };
  return labels[status] || status;
}

async function initGenerationForm() {
  if (!API.requireAuth()) return;

  const templateSelect = document.getElementById('template-select');
  const fieldsContainer = document.getElementById('dynamic-fields');
  const submitBtn = document.getElementById('submit-btn');
  const form = document.getElementById('generation-form');

  // Load templates
  try {
    const templates = await API.getJSON('/api/templates/?limit=100');
    templateSelect.innerHTML = '<option value="">-- Выберите шаблон --</option>' +
      templates.map(t => `<option value="${t.uid}">${escapeHtml(t.name)} (${t.canvas_width}×${t.canvas_height})</option>`).join('');

    // If template_uid is pre-selected
    const preselected = document.getElementById('preselected-template')?.value;
    if (preselected) {
      templateSelect.value = preselected;
      await loadTemplateFields(preselected);
    }
  } catch (e) {
    templateSelect.innerHTML = '<option>Ошибка загрузки шаблонов</option>';
  }

  templateSelect.addEventListener('change', async () => {
    const uid = templateSelect.value;
    if (!uid) {
      fieldsContainer.innerHTML = '';
      return;
    }
    await loadTemplateFields(uid);
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.textContent = 'Генерация...';

    const uid = templateSelect.value;
    if (!uid) {
      alert('Выберите шаблон');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Генерировать';
      return;
    }

    // Collect input data
    const inputData = {};
    document.querySelectorAll('.variable-input').forEach(input => {
      inputData[input.dataset.name] = input.value;
    });

    const outputFormat = document.getElementById('output-format')?.value || 'png';

    try {
      const result = await API.postJSON('/api/generations/', {
        template_uid: uid,
        input_data: inputData,
        output_format: outputFormat,
      });
      window.location = `/generations/${result.uid}`;
    } catch (err) {
      const msg = err?.message || err?.detail?.message || 'Ошибка генерации';
      alert(msg);
      submitBtn.disabled = false;
      submitBtn.textContent = 'Генерировать';
    }
  });
}

async function loadTemplateFields(uid) {
  const fieldsContainer = document.getElementById('dynamic-fields');
  try {
    const tmpl = await API.getJSON(`/api/templates/${uid}`);
    const variables = JSON.parse(tmpl.variables || '[]');
    if (variables.length === 0) {
      fieldsContainer.innerHTML = '<p style="color: var(--secondary);">Нет переменных</p>';
      return;
    }
    fieldsContainer.innerHTML = variables.map(v => `
      <div class="form-group">
        <label class="form-label">${escapeHtml(v.label || v.name)}</label>
        <input
          class="form-control variable-input"
          data-name="${v.name}"
          value="${escapeHtml(v.default || '')}"
          placeholder="${escapeHtml(v.label || v.name)}"
        >
      </div>
    `).join('');
  } catch (e) {
    fieldsContainer.innerHTML = '<p style="color: var(--danger);">Ошибка загрузки полей</p>';
  }
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
