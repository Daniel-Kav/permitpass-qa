// my.html behaviour (kept out of the HTML so the CSP can forbid inline scripts)
document.addEventListener('DOMContentLoaded', async () => {
  if (!PP.requireRole('citizen')) return;
  const rows = document.getElementById('rows'), status = document.getElementById('status');

  // One request per refresh, and only the most recent refresh may render (#43)
  let latest = 0;
  async function load() {
    const ticket = ++latest;
    const page = await PP.api('/applications?limit=100');
    if (ticket !== latest) return;
    if (!page.items.length) { rows.innerHTML = '<tr><td colspan="5" class="muted">No applications yet.</td></tr>'; return; }
    const certs = await Promise.all(page.items.map((a) => a.state === 'issued' || a.state === 'revoked'
      ? PP.api(`/applications/${a.id}/certificate`).catch(() => null) : null));
    if (ticket !== latest) return;
    rows.innerHTML = page.items.map((a, i) => `
      <tr data-id="${a.id}">
        <th scope="row">${PP.esc(a.business_name)}</th>
        <td>${PP.esc(a.kra_pin)}</td>
        <td>${PP.fmtState(a.state)}</td>
        <td>${PP.fmtDate(a.created_at)}</td>
        <td>${next(a, certs[i])}</td>
      </tr>`).join('');
    watch(page.items);
    announce(page.items);
  }

  function next(a, cert) {
    const name = PP.esc(a.business_name);
    if (a.state === 'draft') return `<button data-act="submit" aria-label="Submit ${name}">Submit</button>`;
    if (a.state === 'submitted') {
      const note = a.payment_note ? `<p class="alert error payment-note">${PP.esc(a.payment_note)}</p>` : '';
      return `${note}<button data-act="pay" aria-label="Pay KES ${a.fee_kes} for ${name}">Pay KES ${a.fee_kes.toLocaleString()}</button>`;
    }
    if (a.state === 'payment_pending') return '<span class="pending">Check your phone and enter your M-Pesa PIN to approve the payment…</span>';
    if (a.state === 'paid') return '<span class="muted">Awaiting officer review</span>';
    if (a.state === 'approved') return '<span class="muted">Approved, certificate being issued</span>';
    if (a.state === 'rejected') return `<span>Rejected: ${PP.esc(a.rejection_reason)}</span>`;
    if (cert) return `<a href="${PP.esc(cert.verify_url.replace('/verify/', '/verify.html?n=').replace('?sig=', '&sig='))}">Certificate ${PP.esc(cert.number)}</a>`;
    return '';
  }

  // While any payment is pending, refresh every 2 s so the citizen sees M-Pesa's answer without reloading
  let poll = null;
  function watch(items) {
    const pending = items.some((a) => a.state === 'payment_pending');
    if (pending && !poll) poll = setInterval(() => load().catch(() => {}), 2000);
    if (!pending && poll) { clearInterval(poll); poll = null; }
  }

  // Tell screen-reader users (via the live region) when a payment they started finishes
  const waiting = new Map();
  function announce(items) {
    for (const a of items) {
      if (waiting.has(a.id) && a.state !== 'payment_pending') {
        PP.say(status, a.state === 'paid' ? `Payment received for ${a.business_name}.` : `Payment for ${a.business_name} did not go through.`,
          a.state === 'paid' ? 'success' : 'error');
        waiting.delete(a.id);
      }
    }
  }

  rows.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-act]'); if (!btn) return;
    const tr = btn.closest('tr'), id = tr.dataset.id, act = btn.dataset.act;
    if (act === 'pay') { showPayForm(btn, id); return; }
    btn.disabled = true;
    try {
      const a = await PP.api(`/applications/${id}/${act}`, { method: 'POST' });
      PP.say(status, `${a.business_name} submitted.`);
      await load();
    } catch (ex) { PP.say(status, ex.message, 'error'); btn.disabled = false; }
  });

  function showPayForm(btn, id) {
    const cell = btn.closest('td');
    if (cell.querySelector('.pay-form')) return;
    const form = document.getElementById('pay-tpl').content.firstElementChild.cloneNode(true);
    const input = form.querySelector('input');
    input.id = `phone-${id}`;
    form.querySelector('label').htmlFor = input.id;
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      form.querySelector('button[type=submit]').disabled = true;
      try {
        const a = await PP.api(`/applications/${id}/pay`, { method: 'POST', body: { phone: input.value.trim().replace(/\s+/g, '') } });
        waiting.set(id, true);
        PP.say(status, `Payment request sent to ${input.value.trim()}. Approve it on your phone.`);
        await load();
      } catch (ex) { PP.say(status, ex.message, 'error'); form.querySelector('button[type=submit]').disabled = false; }
    });
    form.querySelector('[data-cancel]').addEventListener('click', () => form.remove());
    cell.appendChild(form);
    input.focus();
  }

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
