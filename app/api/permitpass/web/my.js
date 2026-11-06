// my.html behaviour (kept out of the HTML so the CSP can forbid inline scripts)
document.addEventListener('DOMContentLoaded', async () => {
  if (!PP.requireRole('citizen')) return;
  const rows = document.getElementById('rows'), status = document.getElementById('status');

  async function load() {
    const page = await PP.api('/applications?limit=100');
    if (!page.items.length) { rows.innerHTML = '<tr><td colspan="5" class="muted">No applications yet.</td></tr>'; return; }
    const certs = await Promise.all(page.items.map((a) => a.state === 'issued' || a.state === 'revoked'
      ? PP.api(`/applications/${a.id}/certificate`).catch(() => null) : null));
    rows.innerHTML = page.items.map((a, i) => `
      <tr data-id="${a.id}">
        <th scope="row">${PP.esc(a.business_name)}</th>
        <td>${PP.esc(a.kra_pin)}</td>
        <td>${PP.fmtState(a.state)}</td>
        <td>${PP.fmtDate(a.created_at)}</td>
        <td>${next(a, certs[i])}</td>
      </tr>`).join('');
  }

  function next(a, cert) {
    const name = PP.esc(a.business_name);
    if (a.state === 'draft') return `<button data-act="submit" aria-label="Submit ${name}">Submit</button>`;
    if (a.state === 'submitted') return `<button data-act="pay" aria-label="Pay KES ${a.fee_kes} for ${name}">Pay KES ${a.fee_kes.toLocaleString()}</button>`;
    if (a.state === 'paid') return '<span class="muted">Awaiting officer review</span>';
    if (a.state === 'approved') return '<span class="muted">Approved, certificate being issued</span>';
    if (a.state === 'rejected') return `<span>Rejected: ${PP.esc(a.rejection_reason)}</span>`;
    if (cert) return `<a href="${PP.esc(cert.verify_url.replace('/verify/', '/verify.html?n=').replace('?sig=', '&sig='))}">Certificate ${PP.esc(cert.number)}</a>`;
    return '';
  }

  rows.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-act]'); if (!btn) return;
    btn.disabled = true;
    const id = btn.closest('tr').dataset.id, act = btn.dataset.act;
    try {
      const a = await PP.api(`/applications/${id}/${act}`, { method: 'POST' });
      PP.say(status, act === 'pay' ? `Payment received for ${a.business_name}.` : `${a.business_name} submitted.`);
      await load();
    } catch (ex) { PP.say(status, ex.message, 'error'); btn.disabled = false; }
  });

  const form = document.getElementById('new-app');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const a = await PP.api('/applications', { method: 'POST', body: { business_name: form.business_name.value.trim(), kra_pin: form.kra_pin.value.trim().toUpperCase() } });
      form.reset();
      PP.say(status, `Application for ${a.business_name} created as a draft.`);
      await load();
    } catch (ex) { PP.say(status, ex.message, 'error'); }
  });

  load().catch((ex) => PP.say(status, ex.message, 'error'));
});
