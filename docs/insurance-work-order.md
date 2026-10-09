Insurance and Work Order governance — 2026-10-07

Decisions may be recorded only by active users with registration (orders.create)
or contracts.manage privilege, within their assigned branch. Explicit global
administrators retain global access. Merely viewing an order is insufficient.
This matches the existing registration path that records an external insurer
approval reference; RIS does not grant an insurer approval itself.

A required contract must have a latest APPROVED insurance decision with a
non-empty reference. An unresolved latest request blocks conversion and all
send_mwl callers, including recovery resend, even when fully paid. Cash orders
without a required approval or pending request retain their existing flow.
Updating to an unresolved decision clears the old order reference. The original
status event and audit records remain. Order row locks serialize decision updates
with conversion and resend. No schema, report file, or live financial changes.

Validation: 32 isolated ORM regression tests added, existing Latin Worklist tests
retain exact UTF-8 names with an explicit synthetic order identifier. Full suite
and deployed runtime checks must pass before acceptance. Browser tool currently
fails to initialize (kernel assets path missing); visual UAT remains outstanding.
