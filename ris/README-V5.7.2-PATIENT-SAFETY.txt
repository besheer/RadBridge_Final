RIS Web v5.7.2 Patient Safety
================================
- Doctor can choose DRAFT / PARTIAL / VERIFIED / SECOND VERIFIED / FINAL directly.
- FINAL remains locked; later edits require ADDENDUM.
- Upload dropdown exposes all report states.
- Upload validation reads report content, not just filename.
- DOCX: document body + Word headers inspected.
- ODT: content.xml inspected.
- PDF: text extracted using pypdf.
- DOC: cannot be reliably parsed; treated as WARNING.
- MATCH: Patient ID + Accession confirmed.
- WARNING: identifiers cannot be confidently read; user confirmation required for non-final upload.
- BLOCKED: explicit Patient ID or Accession mismatch.
- FINAL requires a MATCH; warning override cannot finalize.
- Validation result and identifiers are written to Audit.
