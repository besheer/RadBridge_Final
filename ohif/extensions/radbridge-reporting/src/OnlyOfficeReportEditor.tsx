import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

declare global {
  interface Window {
    DocsAPI?: any;
  }
}

type Props = {
  orderId: string;
  studyInstanceUID: string;
  identity: string;
  leaseToken: string;
  onClose: () => void;
  layout?: string;
};

const API_SCRIPT =
  '/onlyoffice/web-apps/apps/api/documents/api.js';

export default function OnlyOfficeReportEditor({
  orderId,
  studyInstanceUID,
  identity,
  leaseToken,
  onClose,
  layout = 'FULL_EDITOR',
}: Props) {
  const editorRef = useRef<any>(null);

  // RB_ONLYOFFICE_REACT_DOM_OWNERSHIP_V1
  // React owns this wrapper; ONLYOFFICE owns only its child.
  const editorHostRef =
    useRef<HTMLDivElement | null>(null);
  // RB_ONLYOFFICE_DIRTY_SYNC_V1
  const documentDirtyRef = useRef(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [workflowBusy, setWorkflowBusy] = useState(false);
  const [workflowMessage, setWorkflowMessage] = useState('');
  const [baseVersionNo, setBaseVersionNo] = useState(0);
  const [reportStatus, setReportStatus] = useState('DRAFT');
  const [documentKey, setDocumentKey] = useState('');
  const [editorReloadToken, setEditorReloadToken] =
    useState(0);

  const [templateOptions, setTemplateOptions] = useState<any[]>([]);
  const [chooseTemplate, setChooseTemplate] = useState(false);
  const [templateChoice, setTemplateChoice] = useState<number | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState(0);

  const [narrowScreen, setNarrowScreen] = useState(window.innerWidth < 1000);
  const viewerPercent = narrowScreen ? 0 : ({
    '50_50': 50, '70_30': 70, '30_70': 30,
  }[layout] || 0);

  useEffect(() => {
    const resize = () => setNarrowScreen(window.innerWidth < 1000);
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  useEffect(() => {
    window.dispatchEvent(new CustomEvent('radbridge-report-layout', {
      detail: { viewerPercent },
    }));
    return () => window.dispatchEvent(new CustomEvent('radbridge-report-layout', {
      detail: { viewerPercent: 0 },
    }));
  }, [viewerPercent]);

  function configUrl() {
    const query = new URLSearchParams();

    if (studyInstanceUID) {
      query.set(
        'StudyInstanceUIDs',
        studyInstanceUID
      );
    }

    if (templateChoice !== null) query.set('template_id', String(templateChoice));

    return (
      `/radbridge-api/api/ohif/report/` +
      `${encodeURIComponent(orderId)}` +
      `/onlyoffice/config?${query.toString()}`
    );
  }

  async function loadOnlyOfficeApi() {
    if (window.DocsAPI?.DocEditor) {
      return;
    }

    await new Promise<void>((resolve, reject) => {
      const existing =
        document.querySelector<HTMLScriptElement>(
          `script[src="${API_SCRIPT}"]`
        );

      if (existing) {
        if (window.DocsAPI?.DocEditor) {
          resolve();
          return;
        }

        existing.addEventListener(
          'load',
          () => resolve(),
          { once: true }
        );

        existing.addEventListener(
          'error',
          () => reject(
            new Error(
              'ONLYOFFICE API failed to load'
            )
          ),
          { once: true }
        );

        return;
      }

      const script =
        document.createElement('script');

      script.src = API_SCRIPT;
      script.async = true;

      script.onload = () => resolve();

      script.onerror = () =>
        reject(
          new Error(
            'ONLYOFFICE API failed to load'
          )
        );

      document.head.appendChild(script);
    });
  }

  function workflowUrl(action: string) {
    const query = new URLSearchParams();

    if (studyInstanceUID) {
      query.set(
        'StudyInstanceUIDs',
        studyInstanceUID
      );
    }

    const base =
      `/radbridge-api/api/ohif/report/` +
      `${encodeURIComponent(orderId)}` +
      `/onlyoffice/${action}`;

    return query.toString()
      ? `${base}?${query.toString()}`
      : base;
  }

  async function forceSaveWorkingCopy() {
    if (!documentKey) {
      throw new Error(
        'ONLYOFFICE_DOCUMENT_KEY_MISSING'
      );
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (identity) {
      headers['X-RadBridge-Doctor-Identity'] =
        identity;
    }

    if (leaseToken) {
      headers['X-RadBridge-Report-Lease'] =
        leaseToken;
    }

    const response = await fetch(
      workflowUrl('forcesave'),
      {
        method: 'POST',
        credentials: 'omit',
        headers,
        body: JSON.stringify({
          document_key: documentKey,
          document_dirty: documentDirtyRef.current,
        }),
      }
    );

    let payload: any = {};

    try {
      payload = await response.json();
    } catch {
      payload = {};
    }

    if (
      !response.ok ||
      payload?.ok === false
    ) {
      throw new Error(
        payload?.message ||
        payload?.error ||
        `ForceSave HTTP ${response.status}`
      );
    }

    if (payload?.forcesaved !== true) {
      throw new Error(
        'ONLYOFFICE_FORCESAVE_NOT_CONFIRMED'
      );
    }
    documentDirtyRef.current = false;
  }

  async function runWorkflowAction(
    action: 'commit-draft' | 'verify' | 'finalize'
  ) {
    if (workflowBusy || loading) {
      return;
    }

    if (
      action === 'finalize' &&
      !window.confirm(
        'Finalize this report? It will become read only.'
      )
    ) {
      return;
    }

    setWorkflowBusy(true);
    setError('');
    setWorkflowMessage('');

    try {
      if (action === 'commit-draft') {
        setWorkflowMessage(
          'Saving latest ONLYOFFICE changes...'
        );

        await forceSaveWorkingCopy();

        setWorkflowMessage(
          'Creating clinical draft...'
        );
      }

      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (identity) {
        headers['X-RadBridge-Doctor-Identity'] =
          identity;
      }

      if (leaseToken) {
        headers['X-RadBridge-Report-Lease'] =
          leaseToken;
      }

      const body =
        action === 'finalize'
          ? {}
          : {
              base_version_no: baseVersionNo,
            };

      const response = await fetch(
        workflowUrl(action),
        {
          method: 'POST',
          credentials: 'omit',
          headers,
          body: JSON.stringify(body),
        }
      );

      let payload: any = {};

      try {
        payload = await response.json();
      } catch {
        payload = {};
      }

      if (
        !response.ok ||
        payload?.ok === false
      ) {
        throw new Error(
          payload?.message ||
          payload?.error ||
          `HTTP ${response.status}`
        );
      }

      const nextVersion =
        Number(payload?.version_no);

      if (Number.isFinite(nextVersion)) {
        setBaseVersionNo(nextVersion);
      }

      if (action === 'commit-draft') {
        setReportStatus('DRAFT');
        setWorkflowMessage(
          `Draft saved · Version ${nextVersion}`
        );
      } else if (action === 'verify') {
        setReportStatus('VERIFIED');
        setWorkflowMessage(
          `Report verified · Version ${nextVersion}`
        );

        // RB_VERIFIED_EDITOR_RELOAD_READONLY_V1
        setEditorReloadToken(
          value => value + 1
        );

      } else {
        setReportStatus('FINAL');
        setWorkflowMessage(
          `Report finalized · Version ${nextVersion}`
        );

        setEditorReloadToken(
          value => value + 1
        );
      }
    } catch (e: any) {
      setError(
        e?.message || String(e)
      );
    } finally {
      setWorkflowBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function start() {
      try {
        setLoading(true);
        setError('');

        const headers: Record<string, string> = {};

        if (identity) {
          headers['X-RadBridge-Doctor-Identity'] =
            identity;
        }

        if (leaseToken) headers['X-RadBridge-Report-Lease'] = leaseToken;
        const optionsResponse = await fetch(workflowUrl('template-options'), {
          credentials: 'omit', headers,
        });
        const options = await optionsResponse.json();
        if (!optionsResponse.ok || options?.ok === false) {
          throw new Error(options?.error || 'Cannot load report templates');
        }
        if (cancelled) return;
        setTemplateOptions(options.templates || []);
        setReportStatus(String(options.report_status || 'DRAFT').toUpperCase());
        if (options.can_initialize && templateChoice === null) {
          setChooseTemplate(true);
          setLoading(false);
          return;
        }
        setChooseTemplate(false);
        await loadOnlyOfficeApi();

        const editorUrl = new URL(configUrl(), window.location.origin);
        if (!options.can_initialize) editorUrl.searchParams.delete('template_id');
        const response = await fetch(
          editorUrl.pathname + editorUrl.search,
          {
            credentials: 'omit',
            headers,
          }
        );

        const payload = await response.json();

        if (
          !response.ok ||
          payload?.ok === false
        ) {
          throw new Error(
            payload?.message ||
            payload?.error ||
            `HTTP ${response.status}`
          );
        }

        if (!window.DocsAPI?.DocEditor) {
          throw new Error(
            'ONLYOFFICE DocsAPI unavailable'
          );
        }

        if (!cancelled) {
          const versionNo =
            Number(payload?.base_version_no ?? 0);

          setBaseVersionNo(
            Number.isFinite(versionNo)
              ? versionNo
              : 0
          );

          setReportStatus(
            String(
              payload?.report_status || 'DRAFT'
            ).toUpperCase()
          );

          setDocumentKey(
            String(
              payload?.config?.document?.key || ''
            )
          );
        }

        if (cancelled) {
          return;
        }

        const config = {
          ...(payload?.config || {}),

          events: {
            ...(payload?.config?.events || {}),

            onAppReady: () => {
              if (!cancelled) {
                setLoading(false);
              }
            },

            onDocumentStateChange: (event: any) => {

              documentDirtyRef.current =

                Boolean(event?.data);

            },


            onError: (event: any) => {
              if (!cancelled) {
                const code =
                  event?.data?.errorCode ??
                  'UNKNOWN';

                const description =
                  event?.data?.errorDescription ??
                  '';

                setError(
                  `ONLYOFFICE error ${code}` +
                  (
                    description
                      ? `: ${description}`
                      : ''
                  )
                );
              }
            },
          },
        };

        const editorHost =
          editorHostRef.current;

        if (!editorHost) {
          throw new Error(
            'ONLYOFFICE_EDITOR_HOST_NOT_FOUND'
          );
        }

        editorHost.replaceChildren();

        const editorElement =
          document.createElement('div');

        const editorElementId =
          `radbridge-onlyoffice-editor-` +
          `${orderId}-${editorReloadToken}`;

        editorElement.id = editorElementId;
        editorElement.style.width = '100%';
        editorElement.style.height = '100%';

        editorHost.appendChild(editorElement);

        editorRef.current =
          new window.DocsAPI.DocEditor(
            editorElementId,
            config
          );

      } catch (e: any) {
        if (!cancelled) {
          setLoading(false);
          setError(
            e?.message || String(e)
          );
        }
      }
    }

    start();

    return () => {
      cancelled = true;

      const editor = editorRef.current;
      editorRef.current = null;

      try {
        editor?.destroyEditor?.();
      } catch {
        // Ignore editor cleanup errors.
      }

      try {
        editorHostRef.current?.replaceChildren();
      } catch {
        // React retains ownership of the stable wrapper.
      }
    };
  }, [
    orderId,
    studyInstanceUID,
    identity,
    editorReloadToken,
    templateChoice,
    leaseToken,
  ]);

  return createPortal(
    <div
      role="dialog"
      aria-modal={viewerPercent === 0}
      aria-label="RadBridge ONLYOFFICE Editor"
      style={{
        position: 'fixed',
        top: 0,
        bottom: 0,
        right: 0,
        left: `${viewerPercent}%`,
        zIndex: 10020,
        display: 'flex',
        flexDirection: 'column',
        background: '#071219',
      }}
    >
      <div
        style={{
          minHeight: '48px',
          flex: '0 0 auto',
          flexWrap: 'wrap',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          padding: '0 14px',
          color: '#fff',
          background: '#0b1820',
          borderBottom: '1px solid #173242',
        }}
      >
        <div>
          <div
            style={{
              fontWeight: 700,
            }}
          >
            RadBridge ONLYOFFICE Report Editor
          </div>

          <div
            style={{
              fontSize: '11px',
              opacity: 0.7,
            }}
          >
            Autosave working copy · Finalization remains in RadBridge
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexWrap: 'wrap',
            justifyContent: 'flex-end',
          }}
        >
          <span
            style={{
              fontSize: '12px',
              fontWeight: 700,
              padding: '5px 9px',
              border: '1px solid #355365',
              borderRadius: '5px',
              background: '#10232e',
            }}
          >
            {reportStatus} · Version {baseVersionNo}
          </span>

          {/* RB_FINAL_ONLYOFFICE_TOOLBAR_READONLY_V1 */}
          {reportStatus !== 'FINAL' && (
            <>
          <button
            type="button"
            disabled={
              workflowBusy ||
              chooseTemplate ||
              loading ||
              reportStatus !== 'DRAFT'
            }
            onClick={() => {
              void runWorkflowAction(
                'commit-draft'
              );
            }}
            style={{
              border: '1px solid #496170',
              borderRadius: '5px',
              padding: '6px 12px',
              background: '#17394a',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            Save Draft
          </button>

          <button
            type="button"
            disabled={
              workflowBusy ||
              chooseTemplate ||
              loading ||
              reportStatus !== 'DRAFT'
            }
            onClick={() => {
              void runWorkflowAction(
                'verify'
              );
            }}
            style={{
              border: '1px solid #496170',
              borderRadius: '5px',
              padding: '6px 12px',
              background: '#14532d',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            ✓ Verify
          </button>

          <button
            type="button"
            disabled={
              workflowBusy ||
              chooseTemplate ||
              loading ||
              reportStatus !== 'VERIFIED'
            }
            onClick={() => {
              void runWorkflowAction(
                'finalize'
              );
            }}
            style={{
              border: '1px solid #496170',
              borderRadius: '5px',
              padding: '6px 12px',
              background: '#7c2d12',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            🔒 Finalize
          </button>
            </>
          )}

          <button
            type="button"
            disabled={workflowBusy}
            onClick={onClose}
            style={{
              border: '1px solid #496170',
              borderRadius: '5px',
              padding: '6px 12px',
              background: '#162832',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            Close Editor
          </button>
        </div>
      </div>

      {chooseTemplate && (
        <div style={{ padding: '20px', color: '#fff', background: '#10232e' }}>
          <h3>Choose a report template</h3>
          <p>The selected template will be filled with patient and examination data. This choice is available before writing starts.</p>
          <label htmlFor="report-template-choice">Template </label>
          <select id="report-template-choice" value={selectedTemplate}
            onChange={event => setSelectedTemplate(Number(event.target.value))}
            style={{ padding: '8px', color: '#111', maxWidth: '100%' }}>
            <option value={0}>Standard report with branch header</option>
            {templateOptions.map(template => <option key={template.id} value={template.id}>{template.name}</option>)}
          </select>
          <button type="button" disabled={!leaseToken} onClick={() => setTemplateChoice(selectedTemplate)}
            style={{ padding: '8px 14px', margin: '8px', color: '#fff', background: '#2563eb' }}>Open report</button>
          {!leaseToken && <p>Acquire the report editing lock before starting.</p>}
          <p><a href="/doctor/templates" target="_blank" rel="noopener noreferrer" style={{ color: '#93c5fd' }}>Upload and manage report templates</a></p>
        </div>
      )}
      {!chooseTemplate && reportStatus === 'DRAFT' && (
        <div style={{ padding: '6px 14px', color: '#cbd5e1', fontSize: '12px' }}>
          Edit this report’s header from Insert → Header &amp; Footer. Templates are selected before writing starts.
        </div>
      )}
      {workflowMessage && (
        <div
          style={{
            padding: '7px 14px',
            color: '#bbf7d0',
            background: '#14532d',
            fontSize: '12px',
          }}
        >
          {workflowMessage}
        </div>
      )}

      {error && (
        <div
          style={{
            padding: '9px 14px',
            color: '#ffb4b4',
            background: '#501e1e',
            fontSize: '12px',
          }}
        >
          {error}
        </div>
      )}

      <div
        style={{
          position: 'relative',
          flex: 1,
          minHeight: 0,
          background: '#fff',
        }}
      >
        {loading && (
          <div
            style={{
              position: 'absolute',
              top: 0,
        bottom: 0,
        right: 0,
        left: `${viewerPercent}%`,
              zIndex: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#101b22',
              color: '#fff',
            }}
          >
            Loading ONLYOFFICE…
          </div>
        )}

        <div
          ref={editorHostRef}
          data-radbridge-onlyoffice-host="true"
          style={{
            width: '100%',
            height: '100%',
          }}
        />
      </div>
    </div>,
    document.body
  );
}
