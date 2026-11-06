// index.html behaviour (kept out of the HTML so the CSP can forbid inline scripts)
document.addEventListener('DOMContentLoaded', () => {
  const role = PP.store.get(PP.ROLE);
  if (PP.store.get(PP.TOKEN) && role) location.replace(PP.home(role));
  const form = document.getElementById('login'), err = document.getElementById('login-error');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    err.hidden = true;
    const btn = form.querySelector('button'); btn.disabled = true;
    try {
      const data = await PP.api('/auth/login', { method: 'POST', auth: false, body: { email: form.email.value, password: form.password.value } });
      PP.store.set(PP.TOKEN, data.access_token); PP.store.set(PP.ROLE, data.role);
      location.assign(PP.home(data.role));
    } catch (ex) { PP.say(err, ex.message, 'error'); } finally { btn.disabled = false; }
  });
});
