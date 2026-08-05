// common.js — runs on every page (included via base.html). Only touches
// elements that exist in base.html's nav, so it's safe everywhere.

function initCommon() {
  const logoutBtn = document.getElementById('nav-logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
      window.location.href = '/login';
    });
  }
  loadNavNotifBadge();
}

async function loadNavNotifBadge() {
  const badge = document.getElementById('nav-notif-badge');
  if (!badge) return;
  try {
    const res = await fetch('/api/notifications', { credentials: 'include' });
    if (res.status === 401) return; // not logged in, no badge
    const data = await res.json();
    if (data.success && data.notifications && data.notifications.length) {
      badge.textContent = `${data.notifications.length} alert${data.notifications.length !== 1 ? 's' : ''}`;
      badge.style.display = 'inline-block';
    }
  } catch (e) { /* badge just stays hidden */ }
}
