// queue.html behaviour (kept out of the HTML so the CSP can forbid inline scripts)
document.addEventListener('DOMContentLoaded', () => {
  if (!PP.requireRole('officer', 'admin')) return;
  const rows = document.getElementById('rows'), status = document.getElementById('status');
  const stateSel = document.getElementById('state'), count = document.getElementById('count');
  const isOfficer = PP.store.get(PP.ROLE) === 'officer';

  const ACTIONS = { paid: ['approve', 'reject'], submitted: ['reject'], approved: ['issue'], issued: ['revoke'] };
  const NEEDS_REASON = new Set(['reject', 'revoke']);
  const LABEL = { approve: 'Approve', reject: 'Reject', issue: 'Issue permit', revoke: 'Revoke' };

  // Only the most recent load may render: an older response that arrives late is dropped (#43)
  let latest = 0;
  async function load() {
    const ticket = ++latest;
    const q = stateSel.value ? `?state=${stateSel.value}&limit=100` : '?limit=100';
    const page = await PP.api(`/applications${q}`);
    if (ticket !== latest) return;
    count.textContent = `${page.total} application${page.total === 1 ? '' : 's'}`;
    rows.innerHTML = page.items.map((a) => `
      <tr data-id="${a.id}" data-name="${PP.esc(a.business_name)}">
        <th scope="row">${PP.esc(a.business_name)}</th>
        <td>${PP.esc(a.kra_pin)}</td>
        <td>${PP.fmtState(a.state)}</td>
        <td>${PP.fmtDate(a.created_at)}</td>
        <td><div class="actions">${isOfficer ? (ACTIONS[a.state] || []).map((act) =>
          `<button data-act="${act}" class="${NEEDS_REASON.has(act) ? 'danger' : ''}" aria-label="${LABEL[act]} ${PP.esc(a.business_name)}">${LABEL[act]}</button>`).join('') : '<span class="muted">View only</span>'}</div></td>
      </tr>`).join('') || '<tr><td colspan="5" class="muted">Nothing here.</td></tr>';
  }

  async function act(tr, action, reason) {
    try {
      const a = await PP.api(`/applications/${tr.dataset.id}/${action}`, { method: 'POST', body: reason ? { reason } : undefined });
      PP.say(status, `${a.business_name}: now ${a.state}.`);
      await load();
    } catch (ex) { PP.say(status, ex.message, 'error'); }
  }

  rows.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-act]');
    if (btn) {
      const tr = btn.closest('tr'), action = btn.dataset.act;
      if (!NEEDS_REASON.has(action)) { btn.disabled = true; act(tr, action); return; }
      const cell = btn.closest('td');
      if (cell.querySelector('.reason-form')) return;
      const form = document.getElementById('reason-tpl').content.firstElementChild.cloneNode(true);
      const id = `reason-${tr.dataset.id}`;
      form.querySelector('label').htmlFor = id;
      form.querySelector('input').id = id;
      form.querySelector('button[type=submit]').textContent = `Confirm ${action}`;
      form.addEventListener('submit', (ev) => { ev.preventDefault(); act(tr, action, form.reason.value.trim()); });
      cell.appendChild(form);
      form.querySelector('input').focus();
    }
    if (e.target.matches('[data-cancel]')) e.target.closest('form').remove();
  });

  stateSel.addEventListener('change', () => load().catch((ex) => PP.say(status, ex.message, 'error')));
  load().catch((ex) => PP.say(status, ex.message, 'error'));
});
