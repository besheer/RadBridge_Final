# Report exports

All 23 registered report/list/analytics views expose CSV, Excel (.xlsx), and PDF
from the same authorized GET view using `?export=csv|xlsx|pdf`. Includes physician
counts and VERIFIED/FINAL cases, financial center and accounting reports,
receivables, earnings and replacement settlements, management/referrals,
executive chart data, operations/TAT/assignment, clinical report lists,
inventory stock/ledger/consumption, financial entries/daily closing and audits.

Downloads reuse the protected view and its filters and data, including branch
scoping already enforced by that view. Existing legacy CSV and financial-center
download URLs delegate to their protected report view. Existing finance/analytics
export.view requirements remain. Other new downloads require the report's own
read permission and an active authenticated user. No role permissions expand.
This feature does not redesign legacy report access policies.

The toolbar and file metadata explicitly describe scope: displayed report data
with existing view limits, except physician VERIFIED/FINAL which exports all
matching cases rather than one 50-row page. Existing dashboard top-N groupings
remain top-N. Filters are retained; date/scope defaults from the rendered view
are recorded where available. No posted HTML, form values, hidden elements,
navigation, buttons, action columns or session material are exported.

CSV uses UTF-8 BOM and neutralizes spreadsheet formula prefixes. Excel embeds
real text cells for identifiers/formula-like strings, numeric amounts/counts,
separate sections, filters, frozen headings and RTL sheet display. PDF embeds
Amiri and shapes Arabic per logical wrapped line; wide tables use column panels
with the first identifying column repeated, and repeating headings/page numbers.
Financial and clinical records are read only. Clinical report PDF/DOCX downloads
and sealed report files remain unchanged. No database migration.

Runtime dependencies: existing reportlab/openpyxl, plus pinned arabic-reshaper
3.0.0 and python-bidi 0.6.6. Font is Amiri-Regular.ttf from Google Fonts
https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf
downloaded 2026-10-08, SHA256
ab391c4147d054c48976e98322ad0eefe1427aa0e0502a12a4c75d80a70cfcd7.
OFL license is distributed alongside the font in assets/fonts/OFL.txt.

Source is based on approved current 4c4e150 and deployed on the same approved
Canary 127.0.0.1:18092; obsolete AGENTS.md R8 paths are not current infrastructure.
Tests cover actual CSV/XLSX/PDF bytes, Arabic embedded font, pagination,
permissions, branch denial, legacy permission bypass prevention and view content
exclusion. Deployment requires clean commit, full-suite pass, source/image
verification, database/document backup and unchanged hashes, authenticated
download smoke and browser desktop/mobile UAT before canonical fast-forward.
