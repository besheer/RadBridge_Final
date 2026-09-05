RIS Web v5.8.1 Assignment Hotfix
==================================
Fixes the global Jinja TemplateSyntaxError in templates/base.html.
Cause: a reports.view permission block for Unassigned was opened and never closed.
The reports navigation is now one balanced block containing:
- Unassigned
- Doctor Workspace
- Reports

All templates were parsed with Jinja before packaging.
All v5.8 Assignment Engine + v5.7.2 Patient Safety logic is preserved.
