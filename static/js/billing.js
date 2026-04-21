async function subscribePro() {
  if (!API.getToken()) { window.location = '/login'; return; }
  try {
    const data = await API.postJSON('/api/billing/subscribe', {
      return_url: window.location.origin + '/billing?success=1',
    });
    window.location = data.confirmation_url;
  } catch(e) {
    const msg = (e && e.detail) ? e.detail : 'Ошибка при создании платежа';
    alert(msg);
  }
}

function showCancelModal() {
  const modal = document.getElementById('cancel-modal');
  if (modal) modal.style.display = 'flex';
}

function hideCancelModal() {
  const modal = document.getElementById('cancel-modal');
  if (modal) modal.style.display = 'none';
}

async function confirmCancelSubscription() {
  try {
    await API.postJSON('/api/billing/cancel', {});
    hideCancelModal();
    const notice = document.createElement('div');
    notice.style.cssText = 'position:fixed;top:80px;right:24px;background:var(--success);color:white;padding:12px 20px;border-radius:8px;z-index:9999;';
    notice.textContent = 'Подписка отменена';
    document.body.appendChild(notice);
    setTimeout(() => { notice.remove(); location.reload(); }, 2000);
  } catch(e) {
    alert('Не удалось отменить подписку');
  }
}
