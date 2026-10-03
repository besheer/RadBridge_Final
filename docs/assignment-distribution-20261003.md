# Fair distribution and whole patient visits

Admin: `/admin/assignment-distribution`; profiles: `/admin/assignment`; visits: `/admin/assignment-visits`.

Choose least active cases (oldest turn breaks ties), round-robin by oldest offer/assignment, or longest waiting with online preference. Existing doctor availability, modality/branch matching and external-center pool remain required. Pending offers reserve capacity for every member examination. Verified/final/cancelled work does not count toward active workload. The lower of the global and doctor profile limits applies.

Multi-examination registration and booking create an explicit shared visit ID. Separate MR/CT/DX registrations can be linked explicitly from the visit page after confirming patient, branch and date. Patient ID alone never links different visits. Existing visit groups must be merged in full. Mixed external centers/intake sources cannot be grouped.

One offer assigns the entire visit in one transaction, after every examination is ready. The doctor must qualify and have capacity for all examinations and belong to every matching special doctor pool. An ineligible preferred doctor is skipped for the whole visit. Visits are never split; if no doctor qualifies the visit stays unassigned with an escalation event. Each examination retains a separate report. Linked offers/worklist rows carry a purple accent plus a textual badge/count.

Offer acceptance timeouts remain in Assignment Strategies. Reading-start deadlines are configured separately by priority, modality and minimum image threshold. Exact priority, then modality, then highest matching image threshold wins. Urgent/STAT percentages apply to wildcard-priority rules. A visit uses its longest member deadline. Initial defaults: DX/CR 5 min, CT 10 min (15 at 500+ images), MR 20 min, fallback 10 min; urgent 50%, STAT 25%, minimum 1 min.

New automatic assignments snapshot their deadline; historical null-deadline assignments remain untouched. Timing changes affect new assignments; the global off switch pauses all withdrawal. Start Reading or an acquired report edit lease protects the complete visit. Saved content/versions, an active lease, a returned case, final/verified/cancelled members or manual assignments protect the whole visit. Timeout withdrawal removes ownership from the entire unstarted automatic visit together, adds audit/in-app notifications and excludes its previous doctor from new offers. Report content/files are never changed by maintenance.

Special rules define eligible doctor pools for emergency priority, procedure-name alternatives such as Fistula/Fistulogram, or explicit operator tags for special technique. Matching pools intersect across all visit examinations. Unknown/disabled explicit tags fail closed. Administrators must designate qualified doctors; specialist qualification is not inferred.

Additive migration: `ris/migrations/sql/20261003_assignment_distribution.sql`. The existing RIS container runs maintenance via a systemd timer every minute. No extra permanent container or port. To pause withdrawals use the admin off switch; browser polling also runs maintenance.

Rollback: stop the maintenance timer and restore the previous RIS container. The additive nullable schema remains compatible with old code; do not restore or drop live data as a routine rollback.

Tests: isolated SQLite regression suite and PostgreSQL concurrency acceptance in a temporary database/container removed in the same operation. PostgreSQL acceptance verifies capacity races, competing group acceptance, start-vs-timeout atomicity and report edit lease protection.

Doctor and assignment coordinator monitors: /admin/assignment-monitor and /coordinator/assignments. Both require assignment.manage; the existing reports.coordinate formatting queue remains separate. Monitoring performs no presence or policy writes. It exposes active examinations, grouped visits, offer reservations, start deadlines and manually protected assignments.
