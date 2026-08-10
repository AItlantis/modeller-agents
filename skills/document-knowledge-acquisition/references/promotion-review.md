# Promotion Review

Generated evidence becomes accepted knowledge only after review.

Use this sequence:

1. Select a candidate from `traceability-matrix.csv`.
2. Open its source Markdown anchor and surrounding section.
3. Check comments and issue records that challenge the candidate.
4. Decide whether the candidate is reusable modelling knowledge or project-specific evidence.
5. If reusable, create or update a discovery draft in `inbox/discovery-drafts/`.
6. Run source-boundary, evidence-quality, sensitivity/privacy and knowledge-architecture review.
7. Promote only reviewed facts into `domains/**`.

Do not promote:

- unresolved reviewer comments;
- rules with unclear population, units, aggregation or formula semantics;
- model-object names not verified against the source model;
- client-specific identifiers into public or internal notes without redaction review;
- generated classifications that have not been checked against the source extract.
