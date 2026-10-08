import DraftWarnings from './DraftWarnings';
import { draftWarningMessages } from './draftWarnings';
import { createReportFetch } from './reportIdentity';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import OnlyOfficeReportEditor from './OnlyOfficeReportEditor';
import ViewerQuotation from './ViewerQuotation';

export default function RadBridgeReportingPanel({ servicesManager, commandsManager }: { servicesManager?: any; commandsManager?: any }) {
  const [data, setData] = useState<any>(null);
  const [activeTool, setActiveTool] = useState('');
  const [dictatedText, setDictatedText] = useState('');
  const [dictationLanguage, setDictationLanguage] = useState('en-US');
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const speechAvailable = !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  const [returnReason, setReturnReason] = useState('');
  const [returnNote, setReturnNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [draftWarnings, setDraftWarnings] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [selectedWordFile, setSelectedWordFile] = useState<File | null>(null);
  const [onlyOfficeEditorOpen, setOnlyOfficeEditorOpen] = useState(false);
  const [preferredEditor, setPreferredEditor] = useState('ONLYOFFICE');
  const [preferredLayout, setPreferredLayout] = useState('50_50');
  const [preferredDisplay, setPreferredDisplay] = useState('CURRENT');
  const [editorLayout, setEditorLayout] = useState('FULL_EDITOR');

  // RadBridge report edit lease.
  // The backend requires a valid lease for every clinical write.
  const [leaseToken, setLeaseToken] = useState('');
  // RB_REPORT_LEASE_TOKEN_REF_V1
  // Keep the active token available to async close handlers.
  const leaseTokenRef = useRef('');
  const [leaseExpiresAt, setLeaseExpiresAt] = useState('');
  const [leaseEditorType, setLeaseEditorType] = useState('ONLYOFFICE');
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);

  const params = useMemo(
    () => new URLSearchParams(window.location.search),
    []
  );

  // RB_ONLYOFFICE_DEDICATED_WINDOW_V1
  const dedicatedOnlyOfficeWindow =
    params.get('radbridgeReportWindow') === 'ONLYOFFICE';

  const onlyOfficeAutoOpenRef = useRef(false);
  // RB_ONLYOFFICE_WINDOW_REFERENCE_V1
  const onlyOfficeWindowRef = useRef<Window | null>(null);

  const orderId =
    params.get('radbridgeOrderId') ||
    params.get('orderId') ||
    '';

  const safeOrderId =
    orderId.replace(/[^a-zA-Z0-9_-]/g, '-');

  const dedicatedOnlyOfficeWindowName =
    `radbridge-onlyoffice-${safeOrderId}`;

  const identity =
    params.get('radbridgeIdentity') ||
    '';

  const studyInstanceUID =
    params.get('StudyInstanceUIDs') ||
    params.get('StudyInstanceUID') ||
    '';

  useEffect(() => { setDraftWarnings([]); }, [orderId]);
  const reportFetch = createReportFetch({ orderId: String(orderId), studyInstanceUID, identity });

  function reportApiUrl(suffix = '') {
    const base =
      `/radbridge-api/api/ohif/report/${encodeURIComponent(orderId)}${suffix}`;

    if (!studyInstanceUID) {
      return base;
    }

    const query = new URLSearchParams();
    query.set('StudyInstanceUIDs', studyInstanceUID);

    // Signed doctor identity is already present in the RIS-generated
    // OHIF URL. Include it as an API query fallback because some browser
    // request paths may not preserve the custom identity header.
    if (identity) {
      query.set('radbridgeIdentity', identity);
    }

    return `${base}?${query.toString()}`;
  }

  const accession =
    data?.order?.accession || '';

  const status =
    String(data?.report?.status || 'DRAFT').toUpperCase();

  const locked =
    status === 'VERIFIED' || status === 'FINAL';

  async function changeReportingLayout(layout: string) {
    setError('');
    try {
      const response=await reportFetch(reportApiUrl('/preferences'), {method:'POST', headers:headers(true),body:JSON.stringify({preferred_layout:layout})});
      const result=await response.json();
      if(!response.ok || !result.ok) throw new Error(result.message || 'Could not save reporting layout.');
      setPreferredLayout(result.preferred_layout);
      if(onlyOfficeEditorOpen && ['50_50','70_30','30_70','FULL_EDITOR'].includes(layout)) setEditorLayout(layout);
      setMessage('Reporting layout saved to your profile.');
    } catch(e:any) {setError(e.message || String(e));}
  }

  function openReportingTool(tool: string) {
    setError('');
    const pages: Record<string,string> = {
      Templates:'/doctor/templates',
      'Previous Reports':data?.report?.id ? `/reports/${encodeURIComponent(orderId)}` : '',
      'Clinical Notes':`/orders/${encodeURIComponent(orderId)}/clinical-notes`,
      Attachments:`/orders/${encodeURIComponent(orderId)}/attachments`,
    };
    if(tool in pages){
      if(!pages[tool]) {setError('Load the current report first.');return;}
      const tab=window.open(pages[tool],'_blank','noopener,noreferrer');
      return;
    }
    setActiveTool(activeTool===tool ? '' : tool);
  }

  function exportActiveImage() {
    try {
      const id=servicesManager?.services?.viewportGridService?.getState()?.activeViewportId;
      const viewport=servicesManager?.services?.cornerstoneViewportService?.getCornerstoneViewport(id);
      if(!viewport?.getCurrentImageId?.()) throw new Error('Select and load an image in the viewer first.');
      commandsManager.runCommand('showDownloadViewportModal');
    } catch(e:any){setError(e.message || String(e));}
  }

  function startDictation() {
    if(locked || !speechAvailable || listening) return;
    const Speech=(window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition=new Speech(); recognitionRef.current=recognition;
    recognition.lang=dictationLanguage; recognition.continuous=true; recognition.interimResults=false;
    recognition.onresult=(event:any)=>{
      let text='';for(let i=event.resultIndex;i<event.results.length;i++) if(event.results[i].isFinal) text+=event.results[i][0].transcript+' ';
      if(text) setDictatedText(previous=>(previous+' '+text).trim());
    };
    recognition.onend=()=>setListening(false);
    recognition.onerror=(event:any)=>{setListening(false);setError('Dictation stopped: '+event.error);};
    try{recognition.start();setListening(true);}catch(e:any){setError(e.message || String(e));}
  }
  useEffect(()=>()=>{recognitionRef.current?.abort?.();},[]);
  useEffect(()=>{if(locked) recognitionRef.current?.abort?.();},[locked]);

  function headers(
    json = false,
    includeLease = false,
    tokenOverride = ''
  ) {
    const h: Record<string, string> = {};

    if (json) {
      h['Content-Type'] = 'application/json';
    }

    if (identity) {
      h['X-RadBridge-Doctor-Identity'] = identity;
    }

    const activeLeaseToken =
      tokenOverride || leaseTokenRef.current || leaseToken;

    if (includeLease && activeLeaseToken) {
      h['X-RadBridge-Report-Lease'] = activeLeaseToken;
    }

    return h;
  }

  async function acquireReportLease(
    editorType = 'BROWSER',
    tokenOverride = ''
  ) {
    if (!orderId) {
      throw new Error('Order ID is missing.');
    }

    const token =
      tokenOverride || leaseTokenRef.current || leaseToken;

    const response = await reportFetch(
      reportApiUrl('/lease/acquire'),
      {
        method: 'POST',
        credentials: 'omit',
        headers: headers(true, false),
        body: JSON.stringify({
          editor_type: editorType,
          ...(token ? { lease_token: token } : {}),
        }),
      }
    );

    const payload = await response.json();

    if (!response.ok || payload?.ok === false) {
      throw new Error(
        payload?.message ||
        payload?.reason ||
        payload?.error ||
        `HTTP ${response.status}`
      );
    }

    const newToken = String(payload?.lease_token || '');

    if (!newToken) {
      throw new Error('REPORT_LEASE_TOKEN_MISSING');
    }

    leaseTokenRef.current = newToken;
    setLeaseToken(newToken);
    setLeaseExpiresAt(String(payload?.expires_at || ''));
    setLeaseEditorType(editorType);

    return newToken;
  }

  async function releaseReportLease(tokenOverride = '') {
    const token =
      tokenOverride || leaseTokenRef.current || leaseToken;

    if (!orderId || !token) {
      return;
    }

    try {
      await reportFetch(
        reportApiUrl('/lease/release'),
        {
          method: 'POST',
          keepalive: true,
          credentials: 'omit',
          headers: headers(true, true, token),
          body: JSON.stringify({
            lease_token: token,
          }),
        }
      );
    } catch {
      // Lease expiry is a safe fallback if explicit release fails.
    }

    if (leaseTokenRef.current === token) {
      leaseTokenRef.current = '';
      setLeaseToken('');
      setLeaseExpiresAt('');
    }
  }

  // RB_DEDICATED_WINDOW_LEASE_RELEASE_V1
  // Release the lease when the dedicated browser window is closed.
  useEffect(() => {
    const releaseLeaseOnPageHide = () => {
      const token = leaseTokenRef.current;

      if (!orderId || !token) {
        return;
      }

      leaseTokenRef.current = '';

      void reportFetch(
        reportApiUrl('/lease/release'),
        {
          method: 'POST',
          keepalive: true,
          credentials: 'omit',
          headers: headers(true, true, token),
          body: JSON.stringify({
            lease_token: token,
          }),
        }
      ).catch(() => {
        // Server-side expiry remains the safe fallback.
      });
    };

    window.addEventListener(
      'pagehide',
      releaseLeaseOnPageHide
    );

    return () => {
      window.removeEventListener(
        'pagehide',
        releaseLeaseOnPageHide
      );
    };
  }, [
    dedicatedOnlyOfficeWindow,
    orderId,
    studyInstanceUID,
    identity,
  ]);

  // MultiMonitorService may replace window.name during OHIF startup.
  // Restore the reporting name so subsequent opens reuse this window.
  useEffect(() => {
    if (dedicatedOnlyOfficeWindow) {
      window.name = dedicatedOnlyOfficeWindowName;
    }
  }, [
    dedicatedOnlyOfficeWindow,
    dedicatedOnlyOfficeWindowName,
  ]);

  async function openOnlyOfficeWindow(layout = 'NEW_WINDOW') {
    setError('');

    const trackedWindow = onlyOfficeWindowRef.current;

    if (trackedWindow && !trackedWindow.closed) {
      trackedWindow.focus();
      return;
    }

    const editorUrl = new URL(window.location.href);
    editorUrl.searchParams.set(
      'radbridgeReportWindow',
      'ONLYOFFICE'
    );

    const available = window.screen as any;
    const width = Math.min(layout === 'CASCADE' ? 1200 : 1400, layout === 'CASCADE' ? Math.max(320, available.availWidth - 96) : available.availWidth);
    const height = Math.min(layout === 'CASCADE' ? 850 : 900, layout === 'CASCADE' ? Math.max(320, available.availHeight - 96) : available.availHeight);
    const left = layout === 'CASCADE' ? Math.max(available.availLeft || 0,
      Math.min(window.screenX + 48, (available.availLeft || 0) + available.availWidth - width)) : (available.availLeft || 0);
    const top = layout === 'CASCADE' ? Math.max(available.availTop || 0,
      Math.min(window.screenY + 48, (available.availTop || 0) + available.availHeight - height)) : (available.availTop || 0);
    // Normal pop-out uses a browser tab, including embedded browsers that
    // cannot host popup windows. Geometry is needed only for display layouts.
    const windowFeatures =
      layout === 'CASCADE' || layout === 'DUAL_MONITOR' || preferredDisplay === 'OTHER'
        ? `popup=yes,width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
        : 'popup=no';
    const editorWindow = window.open(
      editorUrl.toString(),
      dedicatedOnlyOfficeWindowName,
      windowFeatures
    );

    if (!editorWindow) {
      setError(
        'The report window was blocked. Allow pop-ups for RadBridge and try again.'
      );
      return;
    }

    onlyOfficeWindowRef.current = editorWindow;

    editorWindow.focus();
    if (layout === 'DUAL_MONITOR' || preferredDisplay === 'OTHER') {
      try {
        const screenDetails = await (window as any).getScreenDetails?.();
        const other = screenDetails?.screens?.find((s: any) => s !== screenDetails.currentScreen);
        if (other) {
          editorWindow.moveTo(other.availLeft, other.availTop);
          editorWindow.resizeTo(other.availWidth, other.availHeight);
        } else {
          setMessage('Move the report window to the other display. Automatic placement is unavailable in this browser.');
        }
      } catch {
        setMessage('Move the report window to the other display. Browser screen permission was not granted.');
      }
    }
  }

  async function openPreferredReport() {
    if (preferredEditor === 'WORD' || preferredEditor === 'LIBREOFFICE') {
      if (!accession) return;
      window.location.href = `risreport://open?accession=${encodeURIComponent(accession)}&editor=${preferredEditor === 'WORD' ? 'word' : 'libreoffice'}`;
      setMessage('Opening the configured desktop reporting agent. DOCX download/upload is also available below.');
      return;
    }
    const popout = ['DUAL_MONITOR', 'CASCADE', 'NEW_WINDOW', 'FULL_VIEWER'].includes(preferredLayout);
    await openReportEditor(popout ? 'ONLYOFFICE' : 'BROWSER', preferredLayout);
  }

  async function openReportEditor(
    editorType: 'ONLYOFFICE' | 'BROWSER',
    layout = 'FULL_EDITOR'
  ) {
    if (!orderId) {
      return;
    }

    // The parent OHIF viewer keeps the diagnostic images visible.
    // The dedicated window owns the editor and its report lease.
    if (
      editorType === 'ONLYOFFICE' &&
      !dedicatedOnlyOfficeWindow
    ) {
      await openOnlyOfficeWindow(layout);
      return;
    }

    setEditorLayout(dedicatedOnlyOfficeWindow ? 'FULL_EDITOR' : layout);

    // Both browser placements use the same DOCX editor and workflow.
    // Verified/final documents open read-only without an editing lease.
    if (locked) {
      setOnlyOfficeEditorOpen(true);
      return;
    }

    setBusy(true);
    setError('');
    setMessage('');

    try {
      await acquireReportLease('ONLYOFFICE');
      setOnlyOfficeEditorOpen(true);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  async function closeReportEditor(
    editorType: 'ONLYOFFICE' | 'BROWSER'
  ) {
    const token = leaseTokenRef.current || leaseToken;

    setOnlyOfficeEditorOpen(false);

    if (token) {
      await releaseReportLease(token);
    }

    if (
      editorType === 'ONLYOFFICE' &&
      dedicatedOnlyOfficeWindow
    ) {
      window.close();
    } else {
      await loadReport();
    }
  }

  function applyData(d: any) {
    setData(d);
  }

  async function loadPreferences() {
    if (!orderId || !identity) {
      setPreferencesLoaded(true);
      return;
    }

    try {
      const response = await reportFetch(
        reportApiUrl('/preferences'),
        {
          method: 'GET',
          headers: headers(),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Preferences request failed (${response.status})`
        );
      }

      const payload = await response.json();

      const editor = String(
        payload?.preferred_editor || 'ONLYOFFICE'
      ).toUpperCase();

      const layout = String(
        payload?.preferred_layout || '50_50'
      ).toUpperCase();

      const allowedEditors = [
        'ONLYOFFICE',
        'BROWSER',
        'WORD',
        'LIBREOFFICE',
        'ASK',
      ];

      const allowedLayouts = [
        '50_50',
        '70_30',
        '30_70',
        'FULL_EDITOR',
        'FULL_VIEWER',
        'DUAL_MONITOR',
        'CASCADE',
        'NEW_WINDOW',
      ];

      setPreferredEditor(
        allowedEditors.includes(editor)
          ? editor
          : 'ONLYOFFICE'
      );

      setPreferredDisplay(payload?.preferred_display === 'OTHER' ? 'OTHER' : 'CURRENT');

      setPreferredLayout(
        allowedLayouts.includes(layout)
          ? layout
          : '50_50'
      );

    } catch (err) {

      console.warn(
        'RadBridge reporting preferences fallback',
        err
      );

      setPreferredEditor('ONLYOFFICE');
      setPreferredLayout('50_50');

    } finally {
      setPreferencesLoaded(true);
    }
  }


  useEffect(() => {
    if (
      !leaseToken ||
      !onlyOfficeEditorOpen
    ) {
      return;
    }

    const timer = window.setInterval(() => {
      acquireReportLease(
        leaseEditorType,
        leaseToken
      ).catch((e: any) => {
        setError(e?.message || String(e));
      });
    }, 60000);

    return () => window.clearInterval(timer);
  }, [
    leaseToken,
    leaseEditorType,
    onlyOfficeEditorOpen,
  ]);

  async function loadReport() {
    if (!orderId) {
      setError(
        'Order ID missing. Open this study from RadBridge RIS.'
      );
      return;
    }

    setBusy(true);
    setError('');
    setMessage('');

    try {
      const r = await reportFetch(
        reportApiUrl(),
        {
          credentials: 'omit',
          headers: headers(false),
        }
      );

      const d = await r.json();

      if (!r.ok || d?.ok === false) {
        throw new Error(
          d?.message ||
          d?.reason ||
          d?.error ||
          `HTTP ${r.status}`
        );
      }

      applyData(d);

      if (
        dedicatedOnlyOfficeWindow &&
        !onlyOfficeAutoOpenRef.current
      ) {
        onlyOfficeAutoOpenRef.current = true;

        const loadedStatus =
          String(
            d?.report?.status || 'DRAFT'
          ).toUpperCase();

        if (
          loadedStatus === 'VERIFIED' ||
          loadedStatus === 'FINAL'
        ) {
          setOnlyOfficeEditorOpen(true);
        } else {
          await acquireReportLease('ONLYOFFICE');
          setOnlyOfficeEditorOpen(true);
        }
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  async function returnCase() {
    if (!orderId || !returnReason) {
      setError('Select return reason first.');
      return;
    }

    setBusy(true);
    setError('');
    setMessage('');

    try {
      const r = await reportFetch(
        reportApiUrl('/return'),
        {
          method: 'POST',
          credentials: 'omit',
          headers: headers(true),
          body: JSON.stringify({
            reason_code: returnReason,
            note: returnNote,
          }),
        }
      );

      const d = await r.json();

      if (!r.ok || d?.ok === false) {
        throw new Error(
          d?.message ||
          d?.reason ||
          d?.error ||
          `HTTP ${r.status}`
        );
      }

      setMessage('Case returned successfully.');
      setReturnReason('');
      setReturnNote('');
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  function openWord() {
    if (!accession) {
      setError('Accession Number unavailable.');
      return;
    }

    window.location.href =
      `risreport://open?accession=${encodeURIComponent(accession)}&editor=word`;
  }


  async function downloadFromRis(
    url: string,
    fallbackName: string
  ) {
    setBusy(true);
    setError('');
    setMessage('');

    try {
      const r = await reportFetch(url, {
        method: 'GET',
        credentials: 'omit',
        headers: headers(false),
      });

      if (!r.ok) {
        let detail = `HTTP ${r.status}`;

        try {
          const d = await r.json();
          detail =
            d?.message ||
            d?.reason ||
            d?.error ||
            detail;
        } catch (_) {}

        throw new Error(detail);
      }

      const blob = await r.blob();

      let filename = fallbackName;

      const disposition =
        r.headers.get('content-disposition') || '';

      const match =
        disposition.match(
          /filename\*?=(?:UTF-8''|")?([^";]+)/i
        );

      if (match?.[1]) {
        filename = decodeURIComponent(
          match[1].replace(/"/g, '')
        );
      }

      const objectUrl =
        window.URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = filename;

      document.body.appendChild(a);
      a.click();
      a.remove();

      window.URL.revokeObjectURL(objectUrl);

      setMessage(`Downloaded ${filename}`);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }


  function downloadAgent() {
    return downloadFromRis(
      '/radbridge-api/api/ohif/reporting-agent/download',
      'RIS-Reporting-Agent-Auto-v2.zip'
    );
  }


  function downloadDicom(format: 'archive' | 'media') {
    const url = new URL(reportApiUrl('/dicom-download'), window.location.origin);
    url.searchParams.set('format', format);
    return downloadFromRis(url.pathname + url.search, `RadBridge-Study-${safeOrderId}-${format}.zip`);
  }

  function downloadWordTemplate() {
    if (!orderId) {
      setError('Order ID is missing.');
      return;
    }

    return downloadFromRis(
      reportApiUrl('/word'),
      `${accession || 'RadBridge-Report'}.docx`
    );
  }


  async function uploadWord(
    action: 'draft' | 'finalize'
  ) {
    if (!orderId) {
      setError('Order ID is missing.');
      return;
    }

    if (!selectedWordFile) {
      setError('Choose a DOCX report first.');
      return;
    }

    if (
      !selectedWordFile.name
        .toLowerCase()
        .endsWith('.docx')
    ) {
      setError(
        'Manual Word workflow currently accepts DOCX files only.'
      );
      return;
    }

    if (locked) {
      setError('FINAL report is locked.');
      return;
    }

    if (
      action === 'finalize' &&
      !window.confirm(
        'Upload and FINALIZE this Word report? The report will be locked.'
      )
    ) {
      return;
    }

    setBusy(true);
    setError('');
    setMessage('');

    try {
      const form = new FormData();

      form.append(
        'document',
        selectedWordFile,
        selectedWordFile.name
      );

      const r = await reportFetch(
        reportApiUrl(`/word/${action}`),
        {
          method: 'POST',
          credentials: 'omit',
          headers: headers(false),
          body: form,
        }
      );

      let d: any = {};

      try {
        d = await r.json();
      } catch (_) {}

      if (!r.ok || d?.ok === false) {
        throw new Error(
          d?.message ||
          d?.reason ||
          d?.error ||
          `HTTP ${r.status}`
        );
      }

      applyData(d);
      setDraftWarnings(action === 'draft' ? draftWarningMessages(d) : []);

      setMessage(
        action === 'finalize'
          ? 'Word report uploaded and finalized successfully.'
          : 'Word draft uploaded successfully.'
      );

      setSelectedWordFile(null);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }


  useEffect(() => {
    loadReport();
    loadPreferences();
  }, []);

  const fieldStyle: React.CSSProperties = {
    width: '100%',
    padding: '9px',
    background: '#071219',
    color: '#fff',
    border: '1px solid #31434e',
    borderRadius: '5px',
    boxSizing: 'border-box',
  };

  const buttonStyle: React.CSSProperties = {
    width: '100%',
    marginTop: '8px',
    padding: '10px',
    cursor: busy ? 'wait' : 'pointer',
  };

  return (
    <div
      style={{
        padding: '16px',
        height: '100%',
        overflowY: 'auto',
        color: '#fff',
        background: '#0b1820',
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: '4px' }}>
        RadBridge Reporting Workspace
      </h3>

      <div
        style={{
          fontSize: '11px',
          opacity: .65,
          marginBottom: '12px'
        }}
      >
        Unified clinical reporting · ONE report · ONE workflow
      </div>

      {error && (
        <div style={{
          background: '#511',
          padding: '9px',
          marginBottom: '10px'
        }}>
          {error}
        </div>
      )}

      <DraftWarnings messages={draftWarnings} />
      {message && (
        <div style={{
          background: '#143b26',
          padding: '9px',
          marginBottom: '10px'
        }}>
          {message}
        </div>
      )}

      <div
        style={{
          background: '#071219',
          padding: '12px',
          marginBottom: '12px',
          borderRadius: '7px',
          border: '1px solid #263845'
        }}
      >
        <div
          style={{
            fontWeight: 800,
            fontSize: '14px',
            marginBottom: '6px'
          }}
        >
          {data?.patient?.name || '-'}
        </div>

        <div
          style={{
            fontSize: '12px',
            lineHeight: 1.55
          }}
        >
          <div>
            <b>Patient ID:</b> {data?.patient?.id || '-'}
          </div>

          <div>
            <b>Accession:</b> {accession || '-'}
          </div>

          <div>
            <b>Study:</b>{' '}
            {[data?.order?.modality, data?.order?.procedure]
              .filter(Boolean)
              .join(' · ') || '-'}
          </div>
        </div>
      </div>

      <div
        style={{
          padding: '10px',
          marginBottom: '12px',
          border: '1px solid #334155',
          borderRadius: '7px'
        }}
      >
        <div
          style={{
            fontSize: '10px',
            opacity: .65,
            marginBottom: '7px',
            fontWeight: 700
          }}
        >
          REPORT WORKFLOW
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            flexWrap: 'wrap'
          }}
        >
          <span
            style={{
              padding: '4px 7px',
              borderRadius: '999px',
              border: '1px solid #475569',
              fontWeight: status === 'DRAFT' ? 800 : 400,
              opacity: status === 'DRAFT' ? 1 : .45
            }}
          >
            DRAFT
          </span>

          <span style={{ opacity: .5 }}>→</span>

          <span
            style={{
              padding: '4px 7px',
              borderRadius: '999px',
              border: '1px solid #475569',
              fontWeight: status === 'VERIFIED' ? 800 : 400,
              opacity: status === 'VERIFIED' ? 1 : .45
            }}
          >
            VERIFIED
          </span>

          <span style={{ opacity: .5 }}>→</span>

          <span
            style={{
              padding: '4px 7px',
              borderRadius: '999px',
              border: '1px solid #475569',
              fontWeight: status === 'FINAL' ? 800 : 400,
              opacity: status === 'FINAL' ? 1 : .45
            }}
          >
            FINAL
          </span>
        </div>

        <div
          style={{
            fontSize: '11px',
            marginTop: '8px'
          }}
        >
          Current status: <strong>{status}</strong>
        </div>
      </div>

      <div
        style={{
          marginBottom: '12px'
        }}
      >
        <div
          style={{
            fontSize: '10px',
            opacity: .65,
            marginBottom: '7px',
            fontWeight: 700
          }}
        >
          REPORT EDITOR
        </div>

        <button disabled={busy || !orderId || !preferencesLoaded}
          style={{ ...buttonStyle, background: '#14532d', fontWeight: 800 }}
          onClick={() => void openPreferredReport()}>
          Open Report · {preferredEditor === 'ASK' ? 'ONLYOFFICE' : preferredEditor} · {preferredLayout}
        </button>
        <a href="/my/profile" target="_blank" rel="noopener noreferrer"
          style={{ display: 'block', margin: '8px 0', color: '#93c5fd' }}>
          My editor &amp; window preferences
        </a>
        <label style={{display:'block',margin:'8px 0'}}>Viewer / report layout
          <select aria-label="Viewer / report layout" value={preferredLayout} disabled={busy || !preferencesLoaded} onChange={e=>void changeReportingLayout(e.target.value)} style={{...fieldStyle,marginTop:6}}>
            <option value="50_50">50% Viewer / 50% Report</option>
            <option value="70_30">70% Viewer / 30% Report</option>
            <option value="30_70">30% Viewer / 70% Report</option>
            <option value="FULL_EDITOR">Full Report</option>
            <option value="FULL_VIEWER">Full Viewer + report window</option>
            <option value="DUAL_MONITOR">Dual Monitor / Pop-out</option>
            <option value="CASCADE">Cascade window</option>
            <option value="NEW_WINDOW">New report window</option>
          </select>
        </label>


        <button
          disabled={busy || !orderId}
          style={{
            ...buttonStyle,
            marginTop: 0,
            fontWeight: 800,
            background: '#17394a'
          }}
          onClick={() => openReportEditor('ONLYOFFICE')}
        >
          {locked
            ? `📄 View ${status} in New Window`
            : '📄 Open ONLYOFFICE in New Window'}
        </button>

        <button
          disabled={busy || !orderId}
          style={buttonStyle}
          onClick={() => openReportEditor('BROWSER', preferredLayout)}
        >
          🌐 Open ONLYOFFICE Here
        </button>

        <div
          style={{
            marginTop: '8px',
            padding: '8px',
            border: '1px solid #334155',
            borderRadius: '6px',
            fontSize: '11px'
          }}
        >
          Primary editor: <strong>{preferredEditor}</strong>
          {' · '}
          Layout: <strong>{preferredLayout}</strong>
          {!preferencesLoaded && ' · Loading…'}
        </div>
      </div>

      <div
        style={{
          fontSize: '10px',
          opacity: .65,
          marginBottom: '7px',
          fontWeight: 700
        }}
      >
        REPORTING TOOLS
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '7px',
          marginBottom: '12px'
        }}
      >
        {[
          ['📄', 'Templates', 'Doctor & study templates'],
          ['🕘', 'Previous Reports', 'Report & version history'],
          ['📝', 'Clinical Notes', 'Clinical history & notes'],
          ['📎', 'Attachments', 'Referral & documents'],
          ['🖼️', 'Key Images', 'Capture selected viewport'],
          ['🎙️', 'Dictation', 'Voice reporting tools']
        ].map(([icon, title, subtitle]) => (
          <button
            type="button"
            onClick={()=>openReportingTool(title)}
            disabled={!orderId || busy}
            key={title}
            style={{
              border: '1px solid #334155',
              borderRadius: '7px',
              padding: '8px',
              minHeight: '54px',
              background: '#0b1820', color:'inherit', textAlign:'left', cursor:'pointer'
            }}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: '11px'
              }}
            >
              {icon} {title}
            </div>

            <div
              style={{
                fontSize: '9px',
                opacity: .6,
                marginTop: '3px'
              }}
            >
              {subtitle}
            </div>
          </button>
        ))}
      </div>

      {activeTool==='Key Images' && <section style={{padding:10,border:'1px solid #334155',marginBottom:12}}>
        <strong>Key image capture</strong>
        <ViewerQuotation servicesManager={servicesManager} reportData={data} />
        <p>Select the image in the viewer, then export a preview. This does not save a DICOM Key Object or attach the image to the report automatically.</p>
        <button type="button" style={buttonStyle} onClick={exportActiveImage}>Export active image</button>
      </section>}
      {activeTool==='Dictation' && <section style={{padding:10,border:'1px solid #334155',marginBottom:12}}>
        <strong>Dictation — review before use</strong>
        <p>Browser speech recognition may use an online speech service. Review and copy the text into ONLYOFFICE; it is not saved to the clinical report automatically.</p>
        {!speechAvailable && <p role="status">This browser does not provide speech recognition. Use a supported browser or your desktop dictation software.</p>}
        {locked && <p role="status">Verified / final report: dictation is disabled.</p>}
        <select aria-label="Dictation language" value={dictationLanguage} disabled={listening} onChange={e=>setDictationLanguage(e.target.value)} style={fieldStyle}><option value="en-US">English</option><option value="ar-EG">العربية — مصر</option></select>
        <button type="button" style={buttonStyle} disabled={locked || !speechAvailable || listening} onClick={startDictation}>Start dictation</button>
        <button type="button" style={buttonStyle} disabled={!listening} onClick={()=>recognitionRef.current?.stop?.()}>Stop dictation</button>
        <textarea aria-label="Dictation review text" value={dictatedText} onChange={e=>setDictatedText(e.target.value)} style={{...fieldStyle,minHeight:120}} />
        <button type="button" style={buttonStyle} disabled={!dictatedText.trim()} onClick={()=>navigator.clipboard.writeText(dictatedText).then(()=>setMessage('Reviewed text copied.')).catch(()=>setError('Copy failed. Select the text and copy it manually.'))}>Copy reviewed text</button>
      </section>}

      <div
        style={{
          padding: '8px',
          marginBottom: '12px',
          borderLeft: '3px solid #475569',
          fontSize: '10px',
          opacity: .7
        }}
      >
        ONLYOFFICE is the primary reporting editor.
        External desktop editors remain optional.
      </div>

      <hr style={{ margin: '16px 0', opacity: .2 }} />

      <div style={{ fontWeight: 700, marginBottom: '8px' }}>Local DICOM Viewer</div>
      <button disabled={busy || !orderId} style={{ ...buttonStyle, width: '100%' }}
        onClick={() => downloadDicom('archive')}>⬇ Download DICOM ZIP · RadiAnt</button>
      <button disabled={busy || !orderId} style={{ ...buttonStyle, width: '100%' }}
        onClick={() => downloadDicom('media')}>📀 CD / USB ZIP · DICOMDIR</button>
      <p style={{ fontSize: '12px', lineHeight: 1.5, opacity: .8 }}>
        Open the downloaded ZIP in RadiAnt, or import its DICOM files into your local viewer.
        Downloads contain the original files for this verified case.
      </p>
      <hr style={{ margin: '16px 0', opacity: .2 }} />

      <div
        style={{
          fontWeight: 700,
          marginBottom: '8px'
        }}
      >
        External DOCX Workflow (Optional)
      </div>

      <button
        disabled={busy || !orderId}
        style={{ ...buttonStyle, marginTop: 0 }}
        onClick={downloadWordTemplate}
      >
        ⬇ Download Current Report DOCX
      </button>

      <input
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disabled={busy || locked}
        onChange={e =>
          setSelectedWordFile(
            e.target.files?.[0] || null
          )
        }
        style={{
          width: '100%',
          marginTop: '10px',
          padding: '8px',
          boxSizing: 'border-box'
        }}
      />

      {selectedWordFile && (
        <div
          style={{
            fontSize: '12px',
            marginTop: '6px',
            opacity: .75
          }}
        >
          Selected: {selectedWordFile.name}
        </div>
      )}

      <button
        disabled={
          busy ||
          locked ||
          !selectedWordFile
        }
        style={buttonStyle}
        onClick={() => uploadWord('draft')}
      >
        ⬆ Upload Word Draft
      </button>

      <button
        disabled={
          busy ||
          locked ||
          !selectedWordFile
        }
        style={{
          ...buttonStyle,
          fontWeight: 700
        }}
        onClick={() => uploadWord('finalize')}
      >
        ⬆ Upload & Finalize Word Report
      </button>

      <hr style={{ margin: '18px 0', opacity: .2 }} />

      <div style={{ fontSize: '12px', lineHeight: 1.5 }}>
        Edit the report document in ONLYOFFICE above. Both opening options use
        the same document, templates and version history. Save Draft, Verify
        and Finalize are available inside the editor.
        {locked && <div>{status} report content is read only.</div>}
      </div>

      <hr style={{ margin: '22px 0', opacity: .2 }} />

      <div style={{ fontWeight: 600 }}>
        Return Case
      </div>

      <select
        value={returnReason}
        disabled={busy}
        onChange={e => setReturnReason(e.target.value)}
        style={{ ...fieldStyle, marginTop: '8px' }}
      >
        <option value="">Select reason...</option>
        <option value="MISSING_HISTORY">Missing clinical history</option>
        <option value="MISSING_REFERRAL">Missing referral / attachment</option>
        <option value="NEED_PRIOR">Need prior / comparison study</option>
        <option value="INCOMPLETE_IMAGES">Incomplete images</option>
        <option value="MISSING_SERIES">Missing series / sequence</option>
        <option value="WRONG_PROTOCOL">Wrong protocol</option>
        <option value="MOTION_ARTIFACT">Motion artifact</option>
        <option value="ADDITIONAL_IMAGING">Additional imaging required</option>
      </select>

      <textarea
        value={returnNote}
        disabled={busy}
        onChange={e => setReturnNote(e.target.value)}
        placeholder="Doctor note..."
        style={{
          ...fieldStyle,
          marginTop: '8px',
          minHeight: '70px'
        }}
      />

      <button
        disabled={busy}
        style={buttonStyle}
        onClick={returnCase}
      >
        Return Case
      </button>

      <button
        disabled={busy}
        style={buttonStyle}
        onClick={loadReport}
      >
        Refresh
      </button>

      {onlyOfficeEditorOpen && (
        <OnlyOfficeReportEditor
          orderId={orderId}
          studyInstanceUID={studyInstanceUID}
          identity={identity}
          leaseToken={leaseToken}
          layout={editorLayout}
          onLayoutChange={dedicatedOnlyOfficeWindow ? undefined : layout=>void changeReportingLayout(layout)}
          onClose={() => {
            void closeReportEditor('ONLYOFFICE');
          }}
        />
      )}

    </div>
  );
}
