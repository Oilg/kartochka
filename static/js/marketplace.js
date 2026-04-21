const WB_HELP = `
  <ol style="padding-left:20px; line-height:2;">
    <li>Войдите в личный кабинет <a href="https://seller.wildberries.ru" target="_blank">Wildberries</a></li>
    <li>Перейдите: Настройки → Доступ к API</li>
    <li>Нажмите "Создать новый токен"</li>
    <li>Выберите права: <strong>Контент</strong></li>
    <li>Скопируйте токен и вставьте выше</li>
  </ol>
`;

const OZON_HELP = `
  <ol style="padding-left:20px; line-height:2;">
    <li>Войдите в <a href="https://seller.ozon.ru" target="_blank">Ozon Seller</a></li>
    <li>Перейдите: Настройки → API ключи</li>
    <li>Нажмите "Создать ключ"</li>
    <li>Скопируйте <strong>Client ID</strong> и <strong>API ключ</strong></li>
    <li>Вставьте оба значения в форму выше</li>
  </ol>
`;

async function loadCredentials() {
  try {
    const creds = await API.getJSON('/api/marketplace-credentials/');
    creds.forEach(c => {
      const mp = c.marketplace;
      const statusEl = document.getElementById(`${mp === 'wildberries' ? 'wb' : 'ozon'}-status`);
      if (statusEl) {
        statusEl.textContent = c.is_valid ? 'подключён ✓' : 'ошибка ключа';
        statusEl.style.color = c.is_valid ? 'var(--success)' : 'var(--danger)';
      }
      const prefix = mp === 'wildberries' ? 'wb' : 'ozon';
      const verifyBtn = document.getElementById(`${prefix}-verify-btn`);
      const deleteBtn = document.getElementById(`${prefix}-delete-btn`);
      if (verifyBtn) verifyBtn.style.display = 'inline-block';
      if (deleteBtn) deleteBtn.style.display = 'inline-block';

      // Set publish mode
      const modeInputs = document.querySelectorAll(`input[name="${prefix}-publish-mode"]`);
      modeInputs.forEach(r => { r.checked = r.value === c.publish_mode; });
    });
  } catch(e) {}
}

async function saveCredential(marketplace) {
  const prefix = marketplace === 'wildberries' ? 'wb' : 'ozon';
  const apiKey = document.getElementById(`${prefix}-api-key`).value.trim();
  const clientId = prefix === 'ozon' ? (document.getElementById('ozon-client-id').value.trim() || null) : null;
  const modeInput = document.querySelector(`input[name="${prefix}-publish-mode"]:checked`);
  const publishMode = modeInput ? modeInput.value : 'manual';

  if (!apiKey) { showMsg(prefix, 'Введите API-ключ', 'error'); return; }
  if (marketplace === 'ozon' && !clientId) { showMsg(prefix, 'Введите Client ID', 'error'); return; }

  showMsg(prefix, 'Сохранение...', 'info');
  try {
    const body = { marketplace, api_key: apiKey, publish_mode: publishMode };
    if (clientId) body.client_id = clientId;
    const cred = await API.postJSON('/api/marketplace-credentials/', body);
    showMsg(prefix, cred.is_valid ? 'Подключено и проверено ✓' : 'Сохранено, но ключ недействителен', cred.is_valid ? 'success' : 'warning');
    await loadCredentials();
  } catch(e) {
    showMsg(prefix, e.detail || 'Ошибка сохранения', 'error');
  }
}

async function verifyCredential(marketplace) {
  const prefix = marketplace === 'wildberries' ? 'wb' : 'ozon';
  showMsg(prefix, 'Проверка...', 'info');
  try {
    const cred = await API.postJSON(`/api/marketplace-credentials/${marketplace}/verify`, {});
    showMsg(prefix, cred.is_valid ? 'Ключ действителен ✓' : 'Ключ недействителен ✗', cred.is_valid ? 'success' : 'error');
  } catch(e) {
    showMsg(prefix, 'Ошибка проверки', 'error');
  }
}

async function deleteCredential(marketplace) {
  if (!confirm(`Удалить учётные данные ${marketplace}?`)) return;
  const prefix = marketplace === 'wildberries' ? 'wb' : 'ozon';
  try {
    await API.request('DELETE', `/api/marketplace-credentials/${marketplace}`);
    showMsg(prefix, 'Удалено', 'success');
    document.getElementById(`${prefix}-status`).textContent = 'не подключён';
    document.getElementById(`${prefix}-status`).style.color = '';
    document.getElementById(`${prefix}-verify-btn`).style.display = 'none';
    document.getElementById(`${prefix}-delete-btn`).style.display = 'none';
  } catch(e) {
    showMsg(prefix, 'Ошибка удаления', 'error');
  }
}

function showMsg(prefix, text, type) {
  const el = document.getElementById(`${prefix}-message`);
  if (!el) return;
  const colors = { success: 'var(--success)', error: 'var(--danger)', warning: 'var(--warning)', info: 'var(--secondary)' };
  el.textContent = text;
  el.style.color = colors[type] || 'var(--secondary)';
}

function openHelp(mp) {
  document.getElementById('help-title').textContent = mp === 'wb' ? 'Как получить API-ключ Wildberries' : 'Как получить API-ключи Ozon';
  document.getElementById('help-content').innerHTML = mp === 'wb' ? WB_HELP : OZON_HELP;
  document.getElementById('help-modal').style.display = 'flex';
}

function closeHelp() {
  document.getElementById('help-modal').style.display = 'none';
}

// Close modal on outside click
document.addEventListener('click', e => {
  const modal = document.getElementById('help-modal');
  if (modal && e.target === modal) closeHelp();
});
