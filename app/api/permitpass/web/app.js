// Shared helpers for every PermitPass page. No framework, no build step.
const PP = (() => {
  const TOKEN = 'pp.token', ROLE = 'pp.role';
  const store = {
    get: (k) => { try { return sessionStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { sessionStorage.setItem(k, v); } catch { /* private mode */ } },
    clear: () => { try { sessionStorage.clear(); } catch { /* ignore */ } },
  };

  async function api(path, { method = 'GET', body, auth = true } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    const token = store.get(TOKEN);
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    if (res.status === 401 && auth) { logout(); throw new Error('Your session has ended. Please log in again.'); }
    const data = res.headers.get('content-type')?.includes('json') ? await res.json() : null;
    if (!res.ok) throw new Error(errorText(data) || `Request failed (${res.status})`);
    return data;
  }

  function errorText(data) {
    if (!data || !data.detail) return '';
    if (typeof data.detail === 'string') return data.detail;
    return data.detail.map((d) => `${d.loc?.slice(-1)[0] ?? 'field'}: ${d.msg}`).join('; ');
  }

  function requireRole(...roles) {
    const role = store.get(ROLE);
    if (!store.get(TOKEN)) { location.replace('/'); return null; }
    if (!roles.includes(role)) { location.replace(home(role)); return null; }
    return role;
  }

  const home = (role) => ({ citizen: '/my.html', officer: '/queue.html', admin: '/queue.html' }[role] || '/');

  function logout() { store.clear(); location.replace('/'); }

  function say(el, message, kind = 'success') {
    el.className = `alert ${kind}`;
    el.textContent = message;
    el.hidden = false;
  }

  const fmtState = (s) => `<span class="badge s-${s}">${s}</span>`;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtDate = (iso) => new Date(iso).toLocaleString('en-KE', { dateStyle: 'medium', timeStyle: 'short' });

  document.addEventListener('click', (e) => { if (e.target.matches('[data-logout]')) logout(); });

  return { api, store, TOKEN, ROLE, requireRole, home, logout, say, fmtState, esc, fmtDate };
})();
