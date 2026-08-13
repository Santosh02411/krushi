// common.js — runs on every page (included via base.html). Only touches
// elements that exist in base.html's nav, so it's safe everywhere.

function initCommon() {
  initLanguage();

  const logoutBtn = document.getElementById('nav-logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
      window.location.href = '/login';
    });
  }

  const deleteBtn = document.getElementById('nav-delete-btn');
  if (deleteBtn) deleteBtn.addEventListener('click', handleDeleteAccount);

  initThemeToggle();
  initDropdown('nav-more-btn', 'nav-more-panel');
  initDropdown('avatar-btn', 'avatar-panel');
  loadNavNotifBadge();
}

function initThemeToggle() {
  const btn = document.getElementById('theme-toggle-btn');
  if (!btn) return;
  const apply = (theme) => {
    document.documentElement.setAttribute('data-theme', theme);
    btn.textContent = theme === 'dark' ? '☀️' : '🌙';
  };
  apply(localStorage.getItem('krushi-theme') || 'light');
  btn.addEventListener('click', () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    localStorage.setItem('krushi-theme', next);
    apply(next);
  });
}

function initDropdown(btnId, panelId) {
  const btn = document.getElementById(btnId);
  const panel = document.getElementById(panelId);
  if (!btn || !panel) return;
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    panel.classList.toggle('show');
  });
  document.addEventListener('click', (e) => {
    if (!panel.contains(e.target) && e.target !== btn) panel.classList.remove('show');
  });
}

async function handleDeleteAccount() {
  if (!confirm('This permanently deletes your account and all your data (records, logs, history). This cannot be undone. Continue?')) return;
  const password = prompt('Enter your password to confirm account deletion:');
  if (!password) return;

  try {
    const res = await fetch('/api/auth/delete-account', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    const data = await res.json();
    if (!data.success) { alert(data.error || 'Could not delete account.'); return; }
    window.location.href = '/login';
  } catch (e) {
    alert('Could not delete account — please try again.');
  }
}

async function loadNavNotifBadge() {
  const badge = document.getElementById('nav-notif-badge');
  // On the home page, initHomePage() already fetches the full
  // notifications list (which does a live weather call) — fetching it
  // again here just for the badge count doubles that work for no reason.
  if (!badge || document.getElementById('home-notif-list')) return;
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
