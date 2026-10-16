# Progress measures / قياس الإنجاز

Date: 2026-10-16. These measures describe the isolated review branch prepared for draft PR #2; they do not certify production readiness.

| Unit | Measured inventory | What it establishes |
|---|---:|---|
| Persisted tables | 160 | Schema ownership and unchanged captured table contracts |
| Registered web routes | 546 | Preserved URL/method/endpoint registrations; not 546 independent business workflows |
| Functions extracted from the original RIS entry point | 949 / 949 | 100% assigned executable component ownership; not 100% rewritten or framework-independent |
| Component/route/helper owner modules | 32 | 12 application components, 12 route modules, eight web helper modules |
| Migrated legacy modules | 76 / 76 | 100% canonical-owner/alias inventory; mixed workflow dependencies remain |
| Explicit service dependency boundaries | 29 | Registered service modules with enforced import boundaries; one module can implement several operations/routes |
| Legacy runtime imports / files | 21 / 8 | Latest static inventory; started at 27 / 11 |
| Dynamic compatibility namespace calls | 11 | Static inventory; broad runtime bindings still remain |
| Focused inventory/runtime composition checks | 32 passed | Inventory safety, return service and component ownership/hash contracts |
| Focused insurance/runtime composition checks | 46 passed | Insurance routes, outbound Worklist gate and component ownership/hash contracts |
| Focused collection/runtime composition checks | 34 passed | Reception permission, same-branch payment route and component ownership/hash contracts |
| Focused assignment-monitor runtime composition checks | 52 passed | Monitor/distribution routes, explicit-runtime regression and component ownership/hash contracts |
| Focused branch/access suites on review branch | 63 passed | Assignment monitor 10, coordinator assignment 30, offer scope 5, readiness/TAT 14, offer-policy permissions 2, communications permissions 2; run separately |
| Component boundary regression on review branch | 5 passed | Manifest and ownership boundary contracts |
| Latest complete local SQLite suite | 2,164 passed / 5 skipped / 0 failed | Python 3.12 temporary environment; code head `0d2eb91`; full `tools/run_tests.py` |
| Focused stock-transfer scope/policy suites | 16 passed | Synthetic request authorization, central action permission, transfer visibility and cross-branch denial |
| Latest GitHub Actions run | 0 / 9 jobs verifiable | Run 38875171502 reports all nine jobs failed without step summaries or job logs; cause is unknown |
| Direct framework/web/database-client imports inside application services | 0 | Static import inventory; ORM operations through the legacy runtime still remain |
| Stock-transfer scope query adapter | Added | SQLAlchemy query construction moved out of the web extension; handlers and transaction ownership remain legacy |
| Technician and coordinator query adapters | Added | Worklist return-state/filter/search and bulk-assignment search construction now live in infrastructure adapters |

## What a percentage means

Ownership allocation of the captured entry-point functions and migrated modules is complete (100% of those inventories). This is a file/function ownership milestone, not complete dependency inversion.

An explicit service boundary is not the same unit as a web route, a function, a feature or a source line. Therefore dividing service count by route or function count does not measure architecture completion. Port module counts do not measure the fraction of original source rewritten either: compatibility glue, new repositories and reused domain functions have different sizes and responsibilities.

There is currently no reviewed, fixed inventory of all business workflows requiring dependency inversion. Do not present a 60%, 65% or other whole-project architecture estimate as measured progress. A valid overall percentage needs a versioned work breakdown with acceptance criteria, consistent units and an agreed denominator; discoveries may change that denominator transparently.

## Implemented vs. unfinished

The explicit boundaries cover assignment queries/mutations/visits; clinical scope/contact preference persistence; report save/edit lease/correction request-review; replacement settlement; original-lot returns; registration/insurance/demographic request-review; readiness resolutions/search/scheduling/snapshot; collection/closing evidence and mutations; RT course/PET links, external plan records, session commands, support/state records and read projections; returned-document prerequisites. See the executable [port registry](../../ris/application/port_contracts.json) and [code map](../../ris/docs/CODE_MAP.md).

Remaining boundaries include broad runtime bindings, readiness evidence acquisition, coordinator previews/workers, report editor callbacks/finalization/exports, cash receipt/refund/disbursement workflows, inventory consumption/general stock movement, patient creation/booking, broader user lifecycle/import transactions, staff execution, RT permission/configuration lifecycle and external acceptance, and provider/worker lifecycles. These still require a detailed per-use-case census before a total can be stated.

External synthetic integration, browser role UAT, aggregate branch/role visibility, transfer transaction extraction, PostgreSQL/Docker CI verification and upgrade/rollback acceptance remain open. Neither source ownership nor mocked/local tests close those gates. The user has asked to continue through production readiness; the PR remains a draft and no production merge/deployment has occurred.

The previous conversational 60% was a rough estimate, not a code coverage or completion measurement. This document supersedes that estimate with concrete inventories and explicit limitations. [Implementation status](IMPLEMENTATION_STATUS.md) records commit-specific validation.
