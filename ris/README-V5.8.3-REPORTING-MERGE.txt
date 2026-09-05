RIS Web v5.8.3 Reporting Merge
================================
Built on v5.8.2 Stabilized.

Restores the two requested reporting UX behaviors:
1. For any non-final report, the doctor may choose DRAFT / PARTIAL / VERIFIED /
   SECOND VERIFIED / FINAL directly, without forced sequential transitions.
2. Upload Report includes a Report Status dropdown with all five states next to
   the file upload control.

FINAL remains protected; later edits require ADDENDUM.
Patient Safety validation remains enabled.
All v5.8.2 stabilization fixes remain included.
All Jinja templates and Python syntax validated before packaging.
