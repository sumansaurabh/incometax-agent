# 30-Point Finish Plan

Date: 2026-04-22

This document replaces the earlier scaffold-executed checklist. The repository now has a meaningful implemented core across document intake, guided autofill, filing completion, official-artifact attachment, post-filing workflows, auth/session, trust controls, validation help, unsupported-flow downgrade, quarantine, retention, reviewer sign-off, and CA export bundles. The 30 items below cover only the work still required to finish all phases in `docs/PLAN.md`.

## Phase Coverage Map

| Phase | Primary items | What these items close |
|---|---|---|
| Phase 0 - Foundations | 1-5 | production auth/session hardening, consent-first UX, CI quality gates, environment bootstrap, audit export |
| Phase 1 - Portal Copilot | 6-10 | DOM-backed adapter coverage, stronger page detection, broader validation recovery, selector-drift recovery |
| Phase 2 - Document Intelligence | 11-15 | parser breadth, OCR quality, fixture bank, extraction metrics, deeper reconciliation |
| Phase 3 - Guided Autofill | 16-20 | rules breadth, supported taxpayer coverage, inline evidence, broader tested autofill reliability |
| Phase 4 - Completion Flow | 21-25 | official artifacts, ITR-U, CA/reviewer dashboard depth, advanced post-filing operations |
| Phase 5 - Scale And Hardening | 26-30 | replay, drift automation, analytics, security operations, final phase-exit validation |

## 30 Points

### Foundation And Trust

1. Harden extension-side auth and session storage with real encryption, secret rotation, and revocation-safe refresh handling.
2. Add purpose-specific consent onboarding for upload, autofill, regime preview, reviewer sharing, submission, and retention.
3. Turn CI into a hard quality gate by removing allow-failure paths and requiring lint, typecheck, tests, builds, and schema checks to pass.
4. Add environment bootstrap validation for backend, workers, extension, Postgres, storage, and telemetry dependencies.
5. Package approvals, executions, consents, revocations, and purge history into downloadable audit exports.

### Portal Awareness And Adapters

6. Replace the remaining empty page adapters with DOM-backed field schemas and required-input discovery.
7. Expand supported portal-page coverage across the remaining salary, deductions, tax-paid, bank, summary, and edge-branch flows.
8. Upgrade page detection from title and URL heuristics to DOM signatures with confidence reporting and fallbacks.
9. Extend validation-help translation across more page types, field errors, and recovery suggestions.
10. Persist selector-drift learnings and add safe re-run flows after user-assisted field remapping.

### Document Intelligence Quality

11. Expand parser coverage for TIS, salary slips, rent receipts, home-loan certificates, ELSS/PPF/LIC proofs, and broker statements.
12. Improve OCR and layout handling for scanned or low-quality documents, with persisted confidence and failure reasons.
13. Build a 50-plus-case synthetic fixture bank spanning the supported taxpayer personas and document mixes.
14. Add parser regression checks and extraction scorecards by document type, parser version, and field family.
15. Deepen reconciliation logic for salary, bank interest, broker, duplicates, under-reporting, and AIS-prefill anomalies.

### Rules, Reasoning, And Autofill Breadth

16. Expand rules-core for ITR eligibility, required-schedule detection, residential-status reasoning, and disclosure checks.
17. Complete deduction and exemption coverage, including richer 80C and 80D families, 80TTA or 80TTB, HRA, and home-loan edge cases.
18. Implement supported complex-taxpayer flows for capital gains, multi-employer salary, house property, and ITR-4 presumptive cases with explicit escalation boundaries.
19. Surface inline evidence traceability on filled fields, approval cards, and submission summaries.
20. Broaden tested autofill coverage so all supported pages and personas can prepare, approve, execute, read back, and undo reliably.

### Filing, Reviewer, And Post-Filing Completion

21. Broaden the new official-artifact attachment baseline with page-specific capture, stronger parsing, and portal-download automation when the portal exposes it.
22. Implement ITR-U or updated-return workflow with explicit escalation gates and audit coverage.
23. Build a real CA or reviewer dashboard on top of the current shared-thread APIs, including reviewer queues and sign-off management.
24. Broaden the new CA export baseline into a real multi-client operations layer with queue filters, case packaging presets, and dashboard UX.
25. Broaden post-filing workflows with uploaded-notice parsing, refund-status history, and response-packet export on top of the implemented baseline.

### Reliability, Analytics, And Operations

26. Finish the replay harness so failed threads replay against stored checkpoints plus DOM snapshots.
27. Automate portal-drift monitoring with scheduled snapshots, adapter mismatch triage, and regeneration suggestions.
28. Build analytics dashboards for extraction accuracy, approval latency, selector failures, abandonment stage, time-to-file, and review volume.
29. Deepen security operations with anomaly investigation tooling, medium-risk document triage, and purge-evidence dashboards.
30. Run phase-exit validation across personas, replay fixtures, and demo accounts, then close the remaining go or no-go gaps in `docs/PLAN.md`.

## Completion Standard

This plan is complete only when:

- Items 1-10 are backed by authenticated extension-to-backend flows and CI gates that fail fast.
- Items 11-20 are backed by parser accuracy baselines, replayable fixtures, and persona-level autofill validation.
- Items 21-25 are backed by durable filing and post-filing state transitions plus reviewer and operator workflows.
- Items 26-30 are backed by replayability, analytics, operations runbooks, and phase-exit evidence.
