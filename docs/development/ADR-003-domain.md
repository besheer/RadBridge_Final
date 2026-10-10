# Framework-independent domain policies

Clinical workflow, acquisition completion, assignment decisions, patient demographics, exam type selection, intake normalization, imaging resolution, reception readiness and report version/state policies now have canonical implementations below `ris/domain`.

The previous import paths alias the canonical module object. This preserves private helper imports, exception identity, dataclasses and monkeypatches rather than duplicating implementations. Policy bodies are unchanged; acquisition imports now point directly at canonical domain modules.

`tools/check_architecture.py` rejects domain imports outside Python's standard library and the domain package. A subprocess contract loads all these policies with Python `-S`, so Flask, SQLAlchemy and HTTP clients are unavailable. Existing policy tests remain behavioral acceptance checks.

Database-backed operations are not described as pure domain rules merely because their filenames contain “policy”. They still belong to the application/infrastructure migration scope. This extraction does not introduce a second clinical writer, change schema or authorize production deployment.
