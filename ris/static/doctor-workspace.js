/* Personal worklist: no automatic POST retry and no unsafe HTML injection. */
(() => {
  'use strict';
  const root = document.getElementById('rbUnifiedDoctorWorkspace');
  if (!root) return;
  const ar = root.dataset.ar === 'yes';
  const say = (en, arabic) => ar ? arabic : en;
  const offers = document.getElementById('rbWorkspaceOfferRows');
  const cases = document.getElementById('rbWorkspaceCaseRows');
  const message = document.getElementById('rbWorkspaceMessage');
  const search = document.getElementById('rbWorkspaceSearch');
  let rows = [], loading = false, posting = false;
  function node(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function openLink(url) {
    // Backend emits relative, permission-checked URLs; never navigate to payload origins.
    const parsed = new URL(url, location.origin);
    if (parsed.origin !== location.origin || !parsed.pathname.startsWith('/doctor/cases/')) throw new Error('Invalid link');
    return parsed.href;
  }
  function card(c) {
    const el = node('article', undefined, 'rb-case-card');
    const copy = node('div', undefined, 'rb-case-copy');
    copy.append(node('strong', c.accession + ' · ' + c.patient));
    copy.append(node('small', [c.modality, c.procedure, c.status, say('Images: ', 'الصور: ') + c.images].join(' · ')));
    el.append(copy);
    return el;
  }
  function renderCases() {
    cases.replaceChildren();
    const term = search.value.toLocaleLowerCase();
    const selected = rows.filter(c => [c.accession, c.patient, c.modality, c.procedure].join(' ').toLocaleLowerCase().includes(term));
    selected.forEach(c => {
      const el = card(c), link = node('a', say('Images & report', 'الصور والتقرير'), 'btn primary');
      link.href = openLink(c.open_url); link.target = '_blank'; link.rel = 'noopener';
      el.append(link); cases.append(el);
    });
    if (!selected.length) cases.append(node('p', say('No assigned cases match.', 'لا توجد حالات معيّنة مطابقة.')));
  }
  async function refresh() {
    if (loading || posting) return;
    loading = true;
    try {
      const r = await fetch(root.dataset.api, {credentials:'same-origin', cache:'no-store', redirect:'error'});
      if (!r.ok) throw new Error('Session or request failed');
      const data = await r.json();
      if (!data.ok || !Array.isArray(data.cases) || !Array.isArray(data.offers)) throw new Error('Invalid response');
      rows = data.cases; renderCases(); offers.replaceChildren();
      data.offers.forEach(offer => {
        const el = card(offer.case), actions = node('div', undefined, 'actions');
        el.append(node('small', say('Expires: ', 'ينتهي: ') + new Date(offer.expires_at).toLocaleTimeString()));
        ['ACCEPT','REJECT','BUSY'].forEach(action => {
          const labels = {ACCEPT:say('Accept','قبول'),REJECT:say('Reject','رفض'),BUSY:say('Busy','مشغول')};
          const button = node('button', labels[action], 'btn' + (action === 'ACCEPT' ? ' primary' : ''));
          button.type = 'button'; button.onclick = () => respond(offer, action);
          actions.append(button);
        });
        el.append(actions); offers.append(el);
      });
      if (!data.offers.length) offers.append(node('p', say('No pending offers.', 'لا توجد عروض معلّقة.')));
    } catch (_) {
      offers.replaceChildren(); cases.replaceChildren(); rows = [];
      message.textContent = say('Update failed. Check your login, then refresh.', 'تعذر التحديث. تحقق من تسجيل الدخول ثم حدّث الصفحة.');
    } finally { loading = false; }
  }
  async function respond(offer, action) {
    if (posting || loading) return;
    if (action !== 'ACCEPT' && !window.confirm(say('Confirm response for ', 'تأكيد الرد للحالة ') + offer.case.accession + '?')) return;
    posting = true;
    root.querySelectorAll('button').forEach(b => { b.disabled = true; });
    // Open synchronously with the click, so browser popup blockers do not hide acceptance.
    let viewer = action === 'ACCEPT' ? window.open('about:blank', '_blank') : null;
    if (viewer) { viewer.opener = null; viewer.document.title = say('Accepting offer…', 'جارٍ قبول العرض…'); }
    try {
      const r = await fetch(offer.respond_url, {
        method:'POST', credentials:'same-origin', redirect:'error',
        headers:{'X-RadBridge-Workspace':'doctor'},
        body:new URLSearchParams({action})
      });
      const data = await r.json();
      if (!r.ok || !data.ok) throw new Error('Response not confirmed');
      message.textContent = say('Response saved.', 'تم حفظ الرد.');
      if (data.open_url) {
        const url = openLink(data.open_url);
        const link = node('a', say('Open images & report', 'فتح الصور والتقرير'));
        link.href = url; link.target = '_blank'; link.rel = 'noopener'; message.append(link);
        if (viewer && !viewer.closed) viewer.location.replace(url);
      }
    } catch (_) {
      if (viewer && !viewer.closed) viewer.close();
      message.textContent = say('Response not confirmed. Review the updated cases/offers before retrying.', 'لم يتأكد الرد. راجع الحالات والعروض المحدثة قبل إعادة المحاولة.');
    } finally {
      posting = false;
      root.querySelectorAll('button').forEach(b => { b.disabled = false; });
      await refresh();
    }
  }
  const heartbeat = () => { if (root.dataset.heartbeat) fetch(root.dataset.heartbeat, {method:'POST',credentials:'same-origin',redirect:'error'}).catch(() => {}); };
  document.getElementById('rbWorkspaceRefresh').onclick = refresh;
  search.oninput = renderCases;
  refresh(); heartbeat();
  window.setInterval(() => { if (!document.hidden) refresh(); }, 20000);
  window.setInterval(heartbeat, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh(); heartbeat(); } });
})();
