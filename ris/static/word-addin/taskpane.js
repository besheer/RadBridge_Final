/* global Office, Word */
let currentCase = null;

function setStatus(message, kind='info') {
  const el = document.getElementById('status');
  el.textContent = message;
  el.className = 'wa-status ' + kind;
}

function renderDraftWarnings(warnings) {
  let box = document.getElementById('draftWarnings');
  if (!box) {
    box = document.createElement('details');
    box.id = 'draftWarnings';
    box.className = 'wa-status';
    box.style.background = '#fff3cd';
    document.getElementById('status').after(box);
  }
  box.replaceChildren();
  const rows = Array.isArray(warnings) ? warnings.filter(row => row && (row.message_ar || row.message_en)) : [];
  box.hidden = rows.length === 0;
  if (!rows.length) return;
  const summary = document.createElement('summary');
  summary.textContent = `تنبيهات المسودة — الحفظ متاح / Draft notices — saving remains available (${rows.length})`;
  box.append(summary);
  const list = document.createElement('ul');
  for (const row of rows) {
    const li = document.createElement('li');
    li.dir = 'auto';
    li.textContent = [row.message_ar, row.message_en].filter(Boolean).join(' / ');
    list.append(li);
  }
  box.append(list);
}

function setBusy(busy) {
  document.querySelectorAll('button').forEach(b => b.disabled = busy);
}

function extractAccession(text) {
  const match = text.match(/RIS_ACCESSION\s*:\s*([A-Za-z0-9_-]+)/i);
  return match ? match[1] : null;
}

async function readAccessionFromDocument() {
  return Word.run(async context => {
    const body = context.document.body;
    body.load('text');
    await context.sync();
    return extractAccession(body.text || '');
  });
}

function renderCase(data) {
  renderDraftWarnings([]);
  currentCase = data;
  document.getElementById('caseEmpty').hidden = true;
  document.getElementById('caseCard').hidden = false;
  document.getElementById('patientName').textContent = data.patient.name;
  document.getElementById('patientId').textContent = data.patient.id;
  document.getElementById('accession').textContent = data.accession;
  document.getElementById('study').textContent = `${data.modality} · ${data.procedure}`;
  document.getElementById('reportStatus').textContent = data.report.status;
  document.getElementById('reportStatus').className = 'wa-badge ' + data.report.status.toLowerCase();
  const locked = data.report.status === 'FINAL';
  document.getElementById('saveDraft').disabled = locked;
  document.getElementById('verify').disabled =
        locked || data.report.status !== 'DRAFT';
    document.getElementById('finalize').disabled =
        locked || data.report.status !== 'VERIFIED';
}

async function loadCase() {
  setBusy(true); setStatus('Reading Accession Number from this document…');
  try {
    const accession = await readAccessionFromDocument();
    if (!accession) throw new Error('RIS_ACCESSION was not found. Open the Word template from the RIS case.');
    const res = await fetch(`/api/reporting/cases/${encodeURIComponent(accession)}`, { credentials:'include' });
    if (!res.ok) throw new Error('Case not found in RIS.');
    renderCase(await res.json());
    setStatus('Case loaded and linked to RIS.', 'ok');
  } catch (e) { setStatus(e.message || String(e), 'error'); }
  finally { setBusy(false); }
}

function getWholeDocumentBlob() {
  return new Promise((resolve, reject) => {
    Office.context.document.getFileAsync(Office.FileType.Compressed, { sliceSize: 1024 * 1024 }, result => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) return reject(new Error(result.error.message));
      const file = result.value;
      const chunks = new Array(file.sliceCount);
      let index = 0;
      const next = () => {
        if (index >= file.sliceCount) {
          file.closeAsync();
          return resolve(new Blob(chunks, { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }));
        }
        file.getSliceAsync(index, sliceResult => {
          if (sliceResult.status !== Office.AsyncResultStatus.Succeeded) {
            file.closeAsync();
            return reject(new Error(sliceResult.error.message));
          }
          chunks[index] = new Uint8Array(sliceResult.value.data);
          index += 1; next();
        });
      };
      next();
    });
  });
}

function radbridgeCommitId() {
    if (
        globalThis.crypto &&
        typeof globalThis.crypto.randomUUID === 'function'
    ) {
        return globalThis.crypto.randomUUID();
    }

    const bytes = new Uint8Array(16);

    if (
        globalThis.crypto &&
        typeof globalThis.crypto.getRandomValues === 'function'
    ) {
        globalThis.crypto.getRandomValues(bytes);
    } else {
        for (let i = 0; i < bytes.length; i++) {
            bytes[i] = Math.floor(Math.random() * 256);
        }
    }

    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    const h = Array.from(
        bytes,
        b => b.toString(16).padStart(2, '0')
    );

    return (
        h.slice(0,4).join('') + '-' +
        h.slice(4,6).join('') + '-' +
        h.slice(6,8).join('') + '-' +
        h.slice(8,10).join('') + '-' +
        h.slice(10,16).join('')
    );
}

async function uploadCurrentDocument(action) {
  if (!currentCase) await loadCase();
  if (!currentCase) return;
  if (currentCase.report.status === 'FINAL') return setStatus('This report is FINAL and locked.', 'error');
  if (action === 'finalize' && !confirm('Finalize this report? The approved report will be locked.')) return;
  setBusy(true); setStatus(action === 'finalize' ? 'Finalizing report…' : 'Saving draft…');
  try {
    const blob = await getWholeDocumentBlob();
    const form = new FormData();

    const baseVersionNo = Number(
        currentCase.version_no || 0
    );

    if (
        !Number.isInteger(baseVersionNo) ||
        baseVersionNo < 0
    ) {
        throw new Error(
            'Invalid report version. Reload the case and try again.'
        );
    }

    if (
        !currentCase.pending_commit_id ||
        currentCase.pending_commit_base !== baseVersionNo
    ) {
        currentCase.pending_commit_id = radbridgeCommitId();
        currentCase.pending_commit_base = baseVersionNo;
    }

    form.append(
        'document',
        blob,
        `${currentCase.accession}.docx`
    );

    form.append(
        'base_version_no',
        String(baseVersionNo)
    );

    form.append(
        'commit_id',
        currentCase.pending_commit_id
    );
    const res = await fetch(`/api/reporting/cases/${encodeURIComponent(currentCase.accession)}/${action}`, { method:'POST', body:form, credentials:'include' });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || 'RIS rejected the report.');
    const caseRes = await fetch(`/api/reporting/cases/${encodeURIComponent(currentCase.accession)}`, { credentials:'include' });
    renderCase(await caseRes.json());
    setStatus(action === 'finalize' ? 'Report finalized. DOCX/PDF saved in RIS.' : 'Draft saved in RIS.', 'ok');
    renderDraftWarnings(action === 'draft' ? data.draft_warnings : []);
  } catch(e) { setStatus(e.message || String(e), 'error'); }
  finally { setBusy(false); }
}

function openImages() {
  if (!currentCase) return setStatus('Load the case first.', 'error');
  window.open(currentCase.pacs_url, '_blank');
}

function openRis() {
  if (!currentCase) return window.open('/', '_blank');
  window.open(`/reports/${currentCase.id}`, '_blank');
}

Office.onReady(info => {
  if (info.host !== Office.HostType.Word) return;
  document.getElementById('loadCase').addEventListener('click', loadCase);
  
async function verifyCurrentReport() {
    if (!currentCase) await loadCase();
    if (!currentCase) return;

    if (currentCase.report.status === 'FINAL') {
        return setStatus(
            'This report is FINAL and locked.',
            'error'
        );
    }

    const baseVersionNo = Number(
        currentCase.version_no || 0
    );

    if (
        !Number.isInteger(baseVersionNo) ||
        baseVersionNo <= 0
    ) {
        return setStatus(
            'Save the report as Draft before Verify.',
            'error'
        );
    }

    if (!confirm('Verify this report version?')) {
        return;
    }

    setBusy(true);
    setStatus('Verifying report…');

    try {
        const form = new FormData();

        form.append(
            'base_version_no',
            String(baseVersionNo)
        );

        const res = await fetch(
            `/api/reporting/cases/${encodeURIComponent(currentCase.accession)}/verify`,
            {
                method: 'POST',
                body: form,
                credentials: 'include'
            }
        );

        const data = await res.json();

        if (!res.ok || !data.ok) {
            throw new Error(
                data.message ||
                data.error ||
                `HTTP ${res.status}`
            );
        }

        const caseRes = await fetch(
            `/api/reporting/cases/${encodeURIComponent(currentCase.accession)}`,
            { credentials: 'include' }
        );

        if (!caseRes.ok) {
            throw new Error(
                `Case reload failed: HTTP ${caseRes.status}`
            );
        }

        renderCase(await caseRes.json());

        setStatus(
            'Report verified. This version is now authoritative.',
            'ok'
        );

    } catch (e) {
        setStatus(
            e.message || String(e),
            'error'
        );
    } finally {
        setBusy(false);
    }
}

document.getElementById('saveDraft').addEventListener('click', () => uploadCurrentDocument('draft'));
document.getElementById('verify').addEventListener('click', verifyCurrentReport);
  document.getElementById('finalize').addEventListener('click', () => uploadCurrentDocument('finalize'));
  document.getElementById('openImages').addEventListener('click', openImages);
  document.getElementById('openRis').addEventListener('click', openRis);
  loadCase();
});
