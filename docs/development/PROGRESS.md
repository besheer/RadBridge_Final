# Progress measures / قياس الإنجاز

Date: 2026-10-12. These measures describe the isolated development branch; they do not certify production readiness.

| Unit | Measured inventory | What it establishes |
|---|---:|---|
| Persisted tables | 160 | Schema ownership and unchanged captured table contracts |
| Registered web routes | 546 | Preserved URL/method/endpoint registrations; not 546 independent business workflows |
| Functions extracted from the original RIS entry point | 949 / 949 | 100% assigned executable component ownership; not 100% rewritten or framework-independent |
| Component/route/helper owner modules | 32 | 12 application components, 12 route modules, eight web helper modules |
| Migrated legacy modules | 76 / 76 | 100% canonical-owner/alias inventory; mixed workflow dependencies remain |
| Explicit service dependency boundaries | 21 | Registered service modules with enforced import boundaries; one module can implement several operations/routes |
| Full prior-baseline SQLite tests | 1,985 passed / 5 skipped | Includes the RT plan extraction and corrected audit-history test; new session head still needs its own complete CI |
| Independent CI jobs per code head | 9 | SQLite, seven PostgreSQL suites and Docker development smoke; inspect the result for the exact commit |

## What a percentage means

Ownership allocation of the captured entry-point functions and migrated modules is complete (100% of those inventories). This is a file/function ownership milestone, not complete dependency inversion.

An explicit service boundary is not the same unit as a web route, a function, a feature or a source line. Therefore `21/546` or `21/949` does not measure architecture completion. Port module counts do not measure the fraction of original source rewritten either: compatibility glue, new repositories and reused domain functions have different sizes and responsibilities.

There is currently no reviewed, fixed inventory of all business workflows requiring dependency inversion. Do not present a 60%, 65% or other whole-project architecture estimate as measured progress. A valid overall percentage needs a versioned work breakdown with acceptance criteria, consistent units and an agreed denominator; discoveries may change that denominator transparently.

## Implemented vs. unfinished

The explicit boundaries cover assignment queries/mutations/visits; clinical scope; report save/edit lease/correction request-review; replacement settlement; original-lot returns; registration/insurance; readiness resolutions/search/scheduling/snapshot; collection/closing evidence and mutations; RT course/PET links, external plan records and session commands. See the executable [port registry](../../ris/application/port_contracts.json) and [code map](../../ris/docs/CODE_MAP.md).

Remaining boundaries include broad runtime bindings, readiness evidence acquisition, coordinator previews/workers, report editor callbacks/finalization/exports, cash receipt/refund/disbursement workflows, inventory consumption/general stock movement, patient creation/booking, user lifecycle/import/contact handling, staff execution, RT notes/consumables/course state, and provider/worker lifecycles. These still require a detailed per-use-case census before a total can be stated.

External synthetic integration, browser role UAT, aggregate branch/role visibility and upgrade/rollback acceptance remain open. Neither source ownership nor mocked/local tests close those gates. Production merge/deployment is outside the current authorized implementation scope.

The previous conversational 60% was a rough estimate, not a code coverage or completion measurement. This document supersedes that estimate with concrete inventories and explicit limitations. [Implementation status](IMPLEMENTATION_STATUS.md) records commit-specific validation.
