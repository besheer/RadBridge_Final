// Keep renewed credentials outside React state: refreshing must not remount DOCX.
type Context = { orderId: string; studyInstanceUID: string; identity: string };
const sessions = new Map<string, { token: string; until: number; pending?: Promise<string> }>();
const sessionMessage = 'جلسة التقرير غير متاحة. ارجع للنظام وسجّل الدخول وافتح الحالة مجددًا. / Reporting session unavailable. Return to RIS, sign in and reopen this case.';

export function createReportFetch(context: Context) {
  const key = JSON.stringify([context.orderId, context.studyInstanceUID, context.identity]);
  if (!sessions.has(key)) sessions.set(key, { token: context.identity, until: 0 });
  const state = sessions.get(key)!;

  async function renew() {
    if (Date.now() < state.until) return state.token;
    if (!state.pending) {
      state.pending = (async () => {
        const url = new URL(`/api/reporting/identity/${encodeURIComponent(context.orderId)}`, window.location.origin);
        url.searchParams.set('StudyInstanceUIDs', context.studyInstanceUID);
        const response = await fetch(url.toString(), {
          method: 'POST', credentials: 'same-origin', cache: 'no-store',
          headers: { 'X-RadBridge-Doctor-Identity': state.token },
        });
        if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
          state.until = 0;
          throw new Error(sessionMessage);
        }
        const body = await response.json();
        if (!body.ok || !body.identity || !(body.expires_in > 0)) throw new Error(sessionMessage);
        state.token = body.identity;
        state.until = Date.now() + Math.max(0, body.expires_in - 30) * 1000;
        return state.token;
      })().finally(() => { state.pending = undefined; });
    }
    return state.pending;
  }

  return async (input: string, init: RequestInit = {}) => {
    const url = new URL(input, window.location.origin);
    const prefix = `/radbridge-api/api/ohif/report/${encodeURIComponent(context.orderId)}`;
    if (url.origin !== window.location.origin || !(url.pathname === prefix || url.pathname.startsWith(prefix + '/'))) {
      throw new Error('Invalid reporting request scope.');
    }
    // Page-close release is best effort; never delay navigation or replay writes.
    const token = init.keepalive ? state.token : await renew();
    const headers = new Headers(init.headers);
    headers.set('X-RadBridge-Doctor-Identity', token);
    url.searchParams.set('radbridgeIdentity', token);
    const response = await fetch(url.toString(), { ...init, credentials: 'omit', headers });
    if (!response.ok && !response.headers.get('content-type')?.includes('application/json')) {
      return new Response(JSON.stringify({ ok: false, message: sessionMessage }), {
        status: response.status, headers: { 'Content-Type': 'application/json' },
      });
    }
    return response;
  };
}
