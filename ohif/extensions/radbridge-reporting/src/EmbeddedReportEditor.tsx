import React, { useEffect, useRef, useState } from 'react';

type Props = {
  data: any;
  findings: string;
  impression: string;
  busy: boolean;
  message: string;
  error: string;
  onFindingsChange: (value: string) => void;
  onImpressionChange: (value: string) => void;
  onSaveDraft: () => void;
  onFinalize: () => void;
  onClose: () => void;
};

type ActiveSection = 'findings' | 'impression';

export default function EmbeddedReportEditor({
  data,
  findings,
  impression,
  busy,
  message,
  error,
  onFindingsChange,
  onImpressionChange,
  onSaveDraft,
  onFinalize,
  onClose,
}: Props) {
  const findingsRef = useRef<HTMLDivElement | null>(null);
  const impressionRef = useRef<HTMLDivElement | null>(null);

  const [activeSection, setActiveSection] =
    useState<ActiveSection>('findings');

  const accession = data?.order?.accession || '-';

  const study =
    [data?.order?.modality, data?.order?.procedure]
      .filter(Boolean)
      .join(' · ') || '-';

  const status = String(
    data?.report?.status || 'DRAFT'
  ).toUpperCase();

  const locked = status === 'FINAL';

  useEffect(() => {
    if (
      findingsRef.current &&
      findingsRef.current.innerText !== findings
    ) {
      findingsRef.current.innerText = findings || '';
    }
  }, [findings]);

  useEffect(() => {
    if (
      impressionRef.current &&
      impressionRef.current.innerText !== impression
    ) {
      impressionRef.current.innerText = impression || '';
    }
  }, [impression]);

  function currentEditor() {
    return activeSection === 'findings'
      ? findingsRef.current
      : impressionRef.current;
  }

  function focusEditor() {
    currentEditor()?.focus();
  }

  function command(
    commandName: string,
    value?: string
  ) {
    if (locked || busy) return;

    focusEditor();

    document.execCommand(
      commandName,
      false,
      value
    );

    syncCurrentSection();
  }

  function syncCurrentSection() {
    const editor = currentEditor();
    if (!editor) return;

    const value = editor.innerText || '';

    if (activeSection === 'findings') {
      onFindingsChange(value);
    } else {
      onImpressionChange(value);
    }
  }

  function syncEditor(
    section: ActiveSection,
    element: HTMLDivElement
  ) {
    const value = element.innerText || '';

    if (section === 'findings') {
      onFindingsChange(value);
    } else {
      onImpressionChange(value);
    }
  }

  function setBlock(tag: string) {
    command('formatBlock', tag);
  }

  function insertTable() {
    if (locked || busy) return;

    focusEditor();

    const html =
      '<table border="1" style="border-collapse:collapse;width:100%">' +
      '<tbody>' +
      '<tr><td style="padding:6px">&nbsp;</td><td style="padding:6px">&nbsp;</td></tr>' +
      '<tr><td style="padding:6px">&nbsp;</td><td style="padding:6px">&nbsp;</td></tr>' +
      '</tbody></table><p><br></p>';

    document.execCommand(
      'insertHTML',
      false,
      html
    );

    syncCurrentSection();
  }

  function insertPageBreak() {
    if (locked || busy) return;

    focusEditor();

    document.execCommand(
      'insertHTML',
      false,
      '<div style="border-top:1px dashed #888;margin:28px 0;page-break-after:always"></div><p><br></p>'
    );

    syncCurrentSection();
  }

  function findText() {
    const value = window.prompt('Find text');
    if (!value) return;

    window.find(value);
  }

  function replaceText() {
    if (locked || busy) return;

    const find = window.prompt('Find text');
    if (!find) return;

    const replacement =
      window.prompt('Replace with') ?? '';

    const editor = currentEditor();
    if (!editor) return;

    editor.innerText =
      (editor.innerText || '').split(find).join(replacement);

    syncCurrentSection();
  }

  const toolButton: React.CSSProperties = {
    minWidth: '34px',
    height: '32px',
    padding: '4px 9px',
    border: '1px solid #c8c8c8',
    borderRadius: '3px',
    background: '#ffffff',
    color: '#202020',
    cursor: locked || busy ? 'not-allowed' : 'pointer',
    fontSize: '13px',
  };

  const selectStyle: React.CSSProperties = {
    height: '32px',
    border: '1px solid #c8c8c8',
    borderRadius: '3px',
    background: '#ffffff',
    color: '#202020',
  };

  const editableStyle: React.CSSProperties = {
    minHeight: '230px',
    padding: '4px 2px',
    outline: 'none',
    whiteSpace: 'pre-wrap',
    fontFamily: 'Arial, sans-serif',
    fontSize: '12pt',
    lineHeight: 1.55,
    cursor: locked ? 'default' : 'text',
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Browser Report Editor"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        background: '#d8d8d8',
        color: '#111',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          background: '#0b1820',
          color: '#fff',
          padding: '8px 14px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ fontWeight: 700 }}>
            RadBridge Browser Report Editor
          </div>

          <div
            style={{
              fontSize: '12px',
              opacity: 0.8,
              marginTop: '3px',
            }}
          >
            {data?.patient?.name || '-'}
            {' · '}
            {data?.patient?.id || '-'}
            {' · '}
            {accession}
            {' · '}
            {study}
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <span
            style={{
              padding: '4px 9px',
              borderRadius: '12px',
              background:
                status === 'FINAL'
                  ? '#663333'
                  : '#235c3c',
              fontSize: '12px',
              fontWeight: 700,
            }}
          >
            {status}
          </span>

          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            style={{
              ...toolButton,
              background: '#172a34',
              color: '#fff',
              borderColor: '#526771',
            }}
          >
            Close
          </button>
        </div>
      </div>

      <div
        style={{
          background: '#f3f3f3',
          borderBottom: '1px solid #bcbcbc',
          boxShadow: '0 1px 4px rgba(0,0,0,.2)',
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: '22px',
            padding: '5px 14px 2px',
            fontSize: '13px',
          }}
        >
          <strong>Home</strong>
          <span>Insert</span>
          <span>Review</span>
        </div>

        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '5px',
            padding: '6px 12px 9px',
          }}
        >
          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => command('undo')}
            title="Undo"
          >
            ↶
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => command('redo')}
            title="Redo"
          >
            ↷
          </button>

          <span style={{ opacity: 0.35 }}>|</span>

          <select
            style={{ ...selectStyle, width: '130px' }}
            disabled={locked || busy}
            defaultValue="Arial"
            onChange={e =>
              command('fontName', e.target.value)
            }
          >
            <option>Arial</option>
            <option>Calibri</option>
            <option>Times New Roman</option>
            <option>Courier New</option>
            <option>Georgia</option>
          </select>

          <select
            style={{ ...selectStyle, width: '60px' }}
            disabled={locked || busy}
            defaultValue="3"
            onChange={e =>
              command('fontSize', e.target.value)
            }
          >
            <option value="1">8</option>
            <option value="2">10</option>
            <option value="3">12</option>
            <option value="4">14</option>
            <option value="5">18</option>
            <option value="6">24</option>
            <option value="7">36</option>
          </select>

          <button
            style={{ ...toolButton, fontWeight: 700 }}
            disabled={locked || busy}
            onClick={() => command('bold')}
          >
            B
          </button>

          <button
            style={{ ...toolButton, fontStyle: 'italic' }}
            disabled={locked || busy}
            onClick={() => command('italic')}
          >
            I
          </button>

          <button
            style={{
              ...toolButton,
              textDecoration: 'underline',
            }}
            disabled={locked || busy}
            onClick={() => command('underline')}
          >
            U
          </button>

          <input
            type="color"
            title="Text color"
            disabled={locked || busy}
            onChange={e =>
              command('foreColor', e.target.value)
            }
            style={{
              width: '34px',
              height: '32px',
              padding: '2px',
            }}
          />

          <input
            type="color"
            title="Highlight"
            disabled={locked || busy}
            defaultValue="#ffff00"
            onChange={e =>
              command('hiliteColor', e.target.value)
            }
            style={{
              width: '34px',
              height: '32px',
              padding: '2px',
            }}
          />

          <span style={{ opacity: 0.35 }}>|</span>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => command('justifyLeft')}
            title="Align left"
          >
            ≡←
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => command('justifyCenter')}
            title="Center"
          >
            ≡
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => command('justifyRight')}
            title="Align right"
          >
            →≡
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() =>
              command('insertUnorderedList')
            }
            title="Bullets"
          >
            • List
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() =>
              command('insertOrderedList')
            }
            title="Numbering"
          >
            1. List
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => command('outdent')}
          >
            ← Indent
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => command('indent')}
          >
            Indent →
          </button>

          <span style={{ opacity: 0.35 }}>|</span>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => {
              const editor = currentEditor();
              if (editor) editor.dir = 'ltr';
            }}
          >
            LTR
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={() => {
              const editor = currentEditor();
              if (editor) editor.dir = 'rtl';
            }}
          >
            RTL
          </button>

          <select
            style={{ ...selectStyle, width: '105px' }}
            disabled={locked || busy}
            defaultValue=""
            onChange={e => {
              if (e.target.value) {
                setBlock(e.target.value);
              }
              e.target.value = '';
            }}
          >
            <option value="">Styles</option>
            <option value="p">Normal</option>
            <option value="h1">Heading 1</option>
            <option value="h2">Heading 2</option>
            <option value="h3">Heading 3</option>
          </select>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={insertTable}
          >
            Table
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={insertPageBreak}
          >
            Page Break
          </button>

          <button
            style={toolButton}
            onClick={findText}
          >
            Find
          </button>

          <button
            style={toolButton}
            disabled={locked || busy}
            onClick={replaceText}
          >
            Replace
          </button>
        </div>
      </div>

      {(error || message || locked) && (
        <div
          style={{
            padding: '7px 14px',
            fontSize: '13px',
            background: error
              ? '#ffd8d8'
              : locked
                ? '#fff1cf'
                : '#dff3e5',
            color: '#222',
            borderBottom: '1px solid #bbb',
          }}
        >
          {error ||
            message ||
            'FINAL report verified and locked read-only.'}
        </div>
      )}

      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '28px 20px 60px',
          background: '#b8b8b8',
        }}
      >
        <div
          style={{
            width: '794px',
            minHeight: '1123px',
            margin: '0 auto',
            background: '#fff',
            color: '#111',
            boxShadow: '0 2px 12px rgba(0,0,0,.35)',
            boxSizing: 'border-box',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Institutional header - reserved for logo/branding */}
          <header
            contentEditable={false}
            style={{
              minHeight: '105px',
              padding: '28px 58px 18px',
              boxSizing: 'border-box',
              borderBottom: '1px solid #d7d7d7',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '24px',
            }}
          >
            <div
              style={{
                width: '190px',
                minHeight: '55px',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              {/*
                Reserved logo area.
                The real RadBridge/facility logo asset will be connected
                separately; patient data must never occupy this area.
              */}
              <div
                style={{
                  fontSize: '11px',
                  color: '#999',
                  letterSpacing: '.5px',
                }}
              >
                LOGO
              </div>
            </div>

            <div
              style={{
                textAlign: 'right',
              }}
            >
              <div
                style={{
                  fontSize: '18px',
                  fontWeight: 700,
                }}
              >
                RADIOLOGY REPORT
              </div>

              <div
                style={{
                  marginTop: '4px',
                  fontSize: '10px',
                  color: '#777',
                }}
              >
                RadBridge Reporting
              </div>
            </div>
          </header>

          {/* Immutable RIS patient/study demographics */}
          <section
            contentEditable={false}
            aria-label="Patient and study information"
            style={{
              margin: '18px 58px 0',
              border: '1px solid #bfc5c9',
              background: '#f7f8f9',
            }}
          >
            <div
              style={{
                padding: '6px 10px',
                background: '#e9edf0',
                borderBottom: '1px solid #c9ced2',
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '.7px',
              }}
            >
              PATIENT / STUDY INFORMATION
              <span
                style={{
                  float: 'right',
                  fontWeight: 400,
                  color: '#68747b',
                }}
              >
                AUTO FROM RIS · READ ONLY
              </span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                columnGap: '28px',
                rowGap: '7px',
                padding: '11px 12px',
                fontSize: '11px',
                lineHeight: 1.4,
              }}
            >
              <div>
                <strong>Patient:</strong>{' '}
                {data?.patient?.name || '-'}
              </div>

              <div>
                <strong>Patient ID:</strong>{' '}
                {data?.patient?.id || '-'}
              </div>

              <div>
                <strong>Accession:</strong>{' '}
                {accession}
              </div>

              <div>
                <strong>Modality:</strong>{' '}
                {data?.order?.modality || '-'}
              </div>

              <div
                style={{
                  gridColumn: '1 / -1',
                }}
              >
                <strong>Study:</strong>{' '}
                {study}
              </div>
            </div>
          </section>

          {/* Editable report body */}
          <main
            style={{
              flex: 1,
              padding: '30px 76px 44px',
              boxSizing: 'border-box',
            }}
          >
            <section>
              <div
                contentEditable={false}
                style={{
                  fontSize: '15px',
                  fontWeight: 700,
                  marginBottom: '8px',
                }}
              >
                FINDINGS
              </div>

              <div
                ref={findingsRef}
                contentEditable={!locked && !busy}
                suppressContentEditableWarning
                onFocus={() =>
                  setActiveSection('findings')
                }
                onInput={e =>
                  syncEditor(
                    'findings',
                    e.currentTarget
                  )
                }
                style={editableStyle}
              />
            </section>

            <section
              style={{
                marginTop: '34px',
                paddingTop: '22px',
                borderTop: '1px solid #ddd',
              }}
            >
              <div
                contentEditable={false}
                style={{
                  fontSize: '15px',
                  fontWeight: 700,
                  marginBottom: '8px',
                }}
              >
                IMPRESSION
              </div>

              <div
                ref={impressionRef}
                contentEditable={!locked && !busy}
                suppressContentEditableWarning
                onFocus={() =>
                  setActiveSection('impression')
                }
                onInput={e =>
                  syncEditor(
                    'impression',
                    e.currentTarget
                  )
                }
                style={{
                  ...editableStyle,
                  minHeight: '150px',
                }}
              />
            </section>
          </main>

          {/* Reserved document footer */}
          <footer
            contentEditable={false}
            style={{
              minHeight: '78px',
              margin: '0 58px',
              padding: '13px 0 18px',
              borderTop: '1px solid #c8c8c8',
              boxSizing: 'border-box',
              display: 'grid',
              gridTemplateColumns: '1fr auto 1fr',
              alignItems: 'end',
              gap: '12px',
              fontSize: '9px',
              color: '#666',
            }}
          >
            <div>
              <div style={{ fontWeight: 700 }}>
                {locked
                  ? 'FINAL · VERIFIED'
                  : 'DRAFT · NOT VERIFIED'}
              </div>

              <div style={{ marginTop: '3px' }}>
                Radiologist:{' '}
                {data?.report?.radiologist || '-'}
              </div>
            </div>

            <div
              style={{
                textAlign: 'center',
                color: '#888',
              }}
            >
              REPORT FOOTER
            </div>

            <div
              style={{
                textAlign: 'right',
              }}
            >
              <div>
                Accession: {accession}
              </div>

              <div style={{ marginTop: '3px' }}>
                Page 1
              </div>
            </div>
          </footer>
        </div>
      </div>

      <div
        style={{
          minHeight: '56px',
          background: '#0b1820',
          color: '#fff',
          borderTop: '1px solid #31434e',
          padding: '8px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
        }}
      >
        <div
          style={{
            fontSize: '12px',
            display: 'flex',
            gap: '18px',
            alignItems: 'center',
          }}
        >
          <span>
            Patient Safety:{' '}
            <strong>
              {error ? 'BLOCKED' : 'ACTIVE'}
            </strong>
          </span>

          <span>
            Study UID context: <strong>ACTIVE</strong>
          </span>

          <span>
            Status: <strong>{status}</strong>
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            gap: '8px',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            style={{
              ...toolButton,
              background: '#172a34',
              color: '#fff',
              borderColor: '#526771',
            }}
          >
            Close
          </button>

          {!locked && (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={onSaveDraft}
                style={{
                  ...toolButton,
                  minWidth: '110px',
                  background: '#164b69',
                  color: '#fff',
                  borderColor: '#2e7399',
                  fontWeight: 700,
                }}
              >
                {busy ? 'Working...' : 'Save Draft'}
              </button>

              <button
                type="button"
                disabled={busy}
                onClick={onFinalize}
                style={{
                  ...toolButton,
                  minWidth: '165px',
                  background: '#8a3a16',
                  color: '#fff',
                  borderColor: '#b85a2d',
                  fontWeight: 700,
                }}
              >
                FINALIZE & VERIFY
              </button>
            </>
          )}

          {locked && (
            <div
              style={{
                padding: '8px 12px',
                border: '1px solid #7f9448',
                borderRadius: '4px',
                background: '#34431f',
                fontWeight: 700,
                fontSize: '12px',
              }}
            >
              ✓ FINAL VERIFIED · READ ONLY
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
