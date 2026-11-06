// verify.html behaviour (kept out of the HTML so the CSP can forbid inline scripts)
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('verify'), out = document.getElementById('result');
  const TEXT = {
    valid: 'Valid permit',
    revoked: 'This permit has been revoked',
    expired: 'This permit has expired',
    invalid: 'Not a valid PermitPass certificate',
  };
  async function check(number, sig) {
    out.innerHTML = '';
    try {
      const r = await PP.api(`/verify/${encodeURIComponent(number)}?sig=${encodeURIComponent(sig)}`, { auth: false });
      out.innerHTML = `<p class="result ${r.status}" data-status="${r.status}">${TEXT[r.status]}</p>` + (r.business_name
        ? `<dl><dt>Business</dt><dd>${PP.esc(r.business_name)}</dd><dt>Valid until</dt><dd>${PP.fmtDate(r.expires_at)}</dd></dl>` : '');
    } catch (ex) { out.innerHTML = `<p class="alert error">${PP.esc(ex.message)}</p>`; }
  }
  form.addEventListener('submit', (e) => { e.preventDefault(); check(form.number.value.trim(), form.sig.value.trim()); });
  const q = new URLSearchParams(location.search);
  if (q.get('n') && q.get('sig')) { form.number.value = q.get('n'); form.sig.value = q.get('sig'); check(q.get('n'), q.get('sig')); }
});
