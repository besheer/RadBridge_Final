# Technician transition branch scope

The canonical `/orders/<id>/exam-status`, legacy `/technician/<id>/status` (including ARRIVED), and supervisor override route now call the same `technician_queue.scoped_order` guard used by the case workspace, image checks, notes and consumable recording. This guard runs before mutation, readiness lookup, audit/event creation, stock use or post-exam assignment.

Inactive actors, actors without a branch and actors from another branch are denied. Existing explicit wildcard/SUPER_ADMIN access is preserved. Workflow permissions, role transitions, image evidence and override reasons remain enforced by their existing handlers. This closes the cross-branch start finding; the other documented finance/inventory/report readiness gaps are separate work.

Tests cover all four actions for another branch, missing branch and inactive user, same-branch compatibility and global supervisor access. Synthetic deployment UAT must use rejected requests only; no actual exam status or report is changed.
