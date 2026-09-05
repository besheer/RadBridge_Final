# RadBridge Engineering Rules

These rules are mandatory for every human or AI agent working in this repository.

## Source of truth

- This Git repository is the single source of truth.
- Work only in `/opt/radbridge/releases/v5.48.1-r8-consolidated`.
- Never edit application source inside a running container.
- Never copy changes between unrelated source trees.
- Start changes on a dedicated feature or fix branch.
- Keep each commit limited to one coherent change.
- Preserve a clean Git working tree between completed steps.

## Environment discipline

- Use the existing R8 environment only.
- RIS R8 container: `radbridge-ris-oo-canary`, host port `18091`.
- OHIF R8 container: `radbridge-ohif-r8-canary`, host port `8095`.
- Never create additional persistent containers, ports, source copies, or Docker images without explicit user approval.
- Temporary resources are allowed only when essential, must have exact names, and must be removed and verified in the same operation.
- Maintain no more than one current development image and one rollback image per service.
- Do not modify Live or Stage unless the user explicitly authorizes that exact operation.
- Do not alter shared networks, databases, mounts, or service contracts without an inspected and documented requirement.

## Change workflow

1. Confirm the active branch and clean working tree.
2. Inspect the exact current contract using read-only checks.
3. Identify exact files, functions, routes, permissions, containers, mounts, and ports.
4. Make the smallest safe change.
5. Compile and validate templates.
6. Import the application in its real runtime environment.
7. Run automated tests and compare with the documented baseline.
8. Commit the change before starting another feature.
9. Build one development image only when source validation passes.
10. Replace the existing R8 service on its existing port using a controlled rollback.
11. Perform authenticated runtime and visual browser UAT.
12. Merge only after all required UAT checks pass.
13. Remove obsolete test resources immediately after validation.

## Safety

- Diagnosis does not authorize implementation.
- Never run destructive or broad cleanup commands against unresolved targets.
- Resolve exact names and inspect targets before stopping, replacing, or deleting them.
- Never use broad recursive deletion against repository, workspace, home, root, Docker storage, database storage, PACS storage, or report storage.
- Backups and rollback targets must be explicit and validated.
- Never expose passwords, tokens, environment secrets, patient identifiers, or authentication material in command output or logs.
- Synthetic UAT data may be changed only within the explicitly approved test scope.
- PACS/DICOM patient-study-order matching is a patient-safety boundary and must fail closed.
- Technician and nursing roles must never receive report editing permissions.
- Locked, verified, or final reports must remain immutable except through an explicit audited workflow.

## Command protocol

- Send one executable command at a time and wait for its result.
- Every operational command must begin with:

  `clear`

  `history -a`

- Every operational command must end with `clear` followed by a concise `===== GREP RESULT =====` block.
- The result block must state return codes, validation status, changed resources, Live/Stage status, phase, progress, and readiness for the next step.
- Pure file-copy instructions are exempt only when no command execution is involved.
- Do not repeat a failed command before diagnosing its exact log.
- Do not claim success from a compile check alone.

## Testing and acceptance

- Automated tests must be compared with `manifests/RIS_TEST_BASELINE.txt`.
- A known baseline failure is not a new regression, but must remain documented.
- Test role-based access for administrator, reception, nursing, technician, radiologist, finance, and other affected roles.
- Validate allowed actions and direct-URL denial.
- Validate Dashboard, scheduling, nursing, exam workflow, PACS, assignment, reporting, inventory, finance, and administration when affected.
- Perform visual browser review at desktop and narrow viewport widths.
- Check browser console errors and failed network requests.
- A feature is incomplete until source, tests, runtime, permissions, browser behavior, cleanup, and Git state are valid.

## Current UI feature rules

- Dashboard modules must be grouped by clear workflow headings and presented as readable cards.
- Technician workspace may start and complete exams, view thumbnails, open images without reporting context, add technical notes and use permitted attachments and consumables.
- Nursing workspace may manage preparation, clinical history, notes, attachments and consumables, and may view thumbnails and images without reporting context.
- Exam transition controls remain role- and permission-protected.
- Opening images for technician or nursing must not include `radbridgeOrderId`, doctor identity, or reporting controls.
- Thumbnail delivery must be authenticated through RIS and must not expose Orthanc credentials.
