RIS Web v5.4.5 Analytics Hotfix
=================================
Fixes Analytics Internal Server Error:
- analytics() now calculates and passes appointment_stats.
- Adds avg_tat, consumable_cost, outstanding and by_branch.
- Appointment stats honor date/branch filters.
- Consumables cost is calculated from OrderConsumable rows.
- Average report TAT uses scheduled time to finalized_at.
- Rewrites analytics.html so every section is inside the Jinja content block.
- Adds defensive defaults in template to avoid undefined-variable crashes.
- Keeps all v5.4.4 functionality and one Gunicorn worker temporarily.
