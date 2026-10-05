import test from 'node:test';
import assert from 'node:assert/strict';
import { createReportFetch } from './reportIdentity.ts';
globalThis.window = { location: { origin: 'https://ris.example.test' } };
const json = body => new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
let counter = 0;
function setup(handler) {
  const calls = [];
  const context = { orderId: '9', studyInstanceUID: '1.2.3', identity: `signed-original-${++counter}` };
  globalThis.fetch = async (url, init) => { calls.push({ url: new URL(url), init }); return handler(new URL(url), init); };
  return { calls, fetch: createReportFetch(context) };
}
const api = '/radbridge-api/api/ohif/report/9';

test('concurrent requests share renewal and preserve write body and lease', async () => {
  const { calls, fetch } = setup(url => url.pathname.startsWith('/api/reporting/')
    ? json({ ok: true, identity: 'renewed', expires_in: 300 }) : json({ ok: true }));
  await Promise.all([fetch(api), fetch(api + '/draft', {
    method: 'POST', headers: { 'X-RadBridge-Report-Lease': 'lease' }, body: 'clinical-draft',
  })]);
  assert.equal(calls.filter(c => c.url.pathname.startsWith('/api/reporting/')).length, 1);
  const renewal = calls[0];
  assert.equal(renewal.init.credentials, 'same-origin');
  assert.equal(renewal.init.method, 'POST');
  assert.equal(renewal.url.searchParams.get('StudyInstanceUIDs'), '1.2.3');
  const write = calls.find(c => c.url.pathname.endsWith('/draft'));
  assert.equal(write.init.body, 'clinical-draft');
  assert.equal(write.init.headers.get('X-RadBridge-Report-Lease'), 'lease');
  assert.equal(write.init.headers.get('X-RadBridge-Doctor-Identity'), 'renewed');
  assert.equal(write.url.searchParams.get('radbridgeIdentity'), 'renewed');
  assert.equal(write.init.credentials, 'omit');
});

test('expired cache renews before writing without replay', async () => {
  const original = Date.now;
  let now = 1000;
  Date.now = () => now;
  try {
    const { calls, fetch } = setup(url => url.pathname.startsWith('/api/reporting/')
      ? json({ ok: true, identity: 'renewed', expires_in: 300 }) : json({ ok: true }));
    await fetch(api);
    now += 271000;
    await fetch(api + '/finalize', { method: 'POST', body: 'write' });
    assert.equal(calls.filter(c => c.url.pathname.startsWith('/api/reporting/')).length, 2);
    assert.equal(calls.filter(c => c.url.pathname.endsWith('/finalize')).length, 1);
  } finally { Date.now = original; }
});

test('session denial fails closed before clinical request', async () => {
  const { calls, fetch } = setup(() => new Response('<html>Login</html>', { status: 401 }));
  await assert.rejects(fetch(api + '/finalize', { method: 'POST' }), /Return to RIS/);
  assert.equal(calls.length, 1);
});

test('credentials never go to a different origin or case', async () => {
  const { calls, fetch } = setup(() => json({}));
  for (const url of ['https://other.test' + api, api.replace('/9', '/99'), '/api/other']) {
    await assert.rejects(fetch(url), /scope/);
  }
  assert.equal(calls.length, 0);
});

test('HTML API denial produces readable JSON without replay', async () => {
  const { calls, fetch } = setup(url => url.pathname.startsWith('/api/reporting/')
    ? json({ ok: true, identity: 'renewed', expires_in: 300 })
    : new Response('<html>Forbidden</html>', { status: 403 }));
  const response = await fetch(api + '/draft', { method: 'POST' });
  assert.equal(response.status, 403);
  assert.match((await response.json()).message, /Return to RIS/);
  assert.equal(calls.length, 2);
});

test('page close uses best effort cached token and does not renew', async () => {
  const { calls, fetch } = setup(() => json({ ok: true }));
  await fetch(api + '/lease/release', { method: 'POST', keepalive: true });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.keepalive, true);
});
