# Plan And Use-Case Coverage Audit

Date: 2026-04-21

## Status Legend

- Scaffold-complete: the module or API surface exists and roughly matches the folder-level plan, but it does not yet satisfy the full documented outcome or exit criteria.
- Partial: meaningful logic exists, but key behavior, persistence, integration, safety, or validation is still missing.
- Implemented-in-code: the end-to-end repo path exists with durable persistence and automated validation, but live-account or operational exit criteria may still remain.
- Missing: the documented capability is absent or only implied by comments/docs.

## Implementation Update

This audit started as a baseline scaffold review. Since then, the repository has moved materially forward and several statements below are now historically useful but no longer current.

Implemented after the original audit:

- Async Postgres-backed checkpoint persistence and thread resume.
- Document upload/storage, extraction, normalization, evidence persistence, health-insurance parsing, and AIS-vs-doc reconciliation.
- Durable proposals, approvals, executions, undo, and browser-reported read-after-write for guided autofill.
- Completion-flow runtime with persisted `submission_summaries`, `consents`, `everification_status`, `filed_return_artifacts`, and `revision_threads`, plus filing APIs and sidepanel UI.

Validation performed after these implementations:

- `PYTHONPATH=apps/backend/src:apps/workers/src ITX_DATABASE_URL=postgresql://itx:itx@localhost:5432/itx python -m pytest apps/backend/tests/api/test_actions.py apps/backend/tests/api/test_filing.py` passed.
- `PYTHONPATH=apps/backend/src:apps/workers/src python -m compileall apps/backend/src apps/workers/src` passed.
- `pnpm --filter @itx/extension typecheck` passed.

What is still materially pending now is concentrated in Phase 5 from `docs/PLAN.md`: broader taxpayer coverage, CA workspace depth, analytics, retention/revocation, notice/refund flows, and production hardening.

## What Was Reviewed

Documentation reviewed:

- docs/PLAN.md
- docs/IMPLEMENTATION_30_POINT_PLAN.md
- docs/USE_CASES.md
- docs/ARCHITECTURE.md
- docs/DATA_MODEL.md
- docs/SECURITY.md
- docs/FOLDER_STRUCTURE.md

Implementation reviewed:

- apps/backend/src/itx_backend/**
- apps/extension/src/**
- apps/workers/src/itx_workers/**
- packages/action-dsl/**
- packages/portal-adapters/**
- packages/rules-core/**
- packages/tax-schema/**
- tests/**
- .github/workflows/ci.yml

Validation performed:

- `python -m compileall apps/backend/src apps/workers/src packages/rules-core/src` passed.
- `pnpm test` failed in the current checkout because dependencies are not installed and `turbo` is unavailable in `node_modules`.

Representative evidence paths:

- Backend graph and nodes: `apps/backend/src/itx_backend/agent/graph.py`
- In-memory checkpointing: `apps/backend/src/itx_backend/agent/checkpointer.py`
- Minimal auth/doc/action APIs: `apps/backend/src/itx_backend/api/*.py`
- Extension shell and sample state: `apps/extension/src/sidepanel/App.tsx`
- Extension browser actions: `apps/extension/src/content/actions/*.ts`
- Parser stubs: `apps/workers/src/itx_workers/parsers/*.py`
- Empty adapter form schemas: `packages/portal-adapters/src/pages/*.ts`
- CI masking failures: `.github/workflows/ci.yml`
- Missing backend tests: `apps/backend/tests/`

## Executive Summary

The repository is a broad implementation scaffold, not a completed realization of the documented plan.

The strongest areas are:

- backend node coverage for explanation, missing-input generation, fill-plan generation, approval gating, submission summary, and e-verify guidance;
- extension shell structure and a substantial evidence-viewer component;
- selector-drift telemetry, replay-harness scaffolding, and lightweight analytics;
- a narrow deterministic rules-core and shared schema/DSL packages.

The weakest areas are:

- durable persistence and real thread resume behavior;
- real document upload, parsing, normalization, and evidence persistence;
- page adapters and DOM schemas for the portal;
- production auth, consent, retention, and anti-phishing behavior;
- end-to-end browser execution and read-after-write validation;
- automated tests and CI enforcement.

Bottom line:

- No phase in `docs/PLAN.md` meets its documented exit criteria.
- The 30-point "Executed" plan substantially overstates completion.
- Under strict end-to-end criteria, no documented use case is fully complete yet.

## Phase-Level Verdict

| Phase | Verdict | Why |
|---|---|---|
| Phase 0 - Foundations | Partial | Monorepo, backend, extension, CI, and shared packages exist, and checkpoint persistence is now Postgres-backed, but CI/auth/security hardening is still thin. |
| Phase 1 - Portal Copilot | Partial | Page detection, explanation, and evidence UI exist, but adapters return empty schemas and detection is mostly title/URL based. |
| Phase 2 - Document Intelligence | Implemented-in-code | Postgres-backed documents, storage, queueing, extraction, normalization, evidence persistence, and reconciliation are implemented; broader fixture-bank accuracy gates remain to be expanded. |
| Phase 3 - Guided Autofill | Implemented-in-code | Durable proposal/approval/execution persistence, live sidepanel approvals, browser execution/readback, and undo are implemented and validated in tests/typecheck. |
| Phase 4 - Completion Flow | Implemented-in-code | Submission summary, consent ledger, artifact archive, e-verification handoff, and revision branching now have persistence, APIs, and sidepanel flow; live demo-account exit criteria remain unverified. |
| Phase 5 - Scale And Hardening | Early partial | Replay, drift autopilot, offline export, analytics, and CA API scaffolds exist, but coverage, reviewer workflow, advanced security, and dashboards are incomplete. |

## Exit-Criteria Check

`docs/PLAN.md` defines phase exit criteria. None of them are met yet.

Key reasons:

- Extension-to-backend round trip exists, but not as a verified, authenticated, production flow.
- Checkpoints are now persisted in Postgres, but CI quality gates and production auth still lag behind the roadmap.
- CI is not a real quality gate because lint/test are allowed to fail.
- Parser accuracy, replay coverage, persona flows, and live demo validations are not present.
- Submission artifacts, approvals, consents, and filing-runtime records are now durably written for the implemented path, but broader audit export, retention, and operational controls remain incomplete.

## 30-Point Plan Audit

This section re-audits `docs/IMPLEMENTATION_30_POINT_PLAN.md`.

| # | Claimed Item | Actual Status | Notes |
|---|---|---|---|
| 1 | Initialize pnpm + uv + Turbo monorepo | Partial | pnpm, Turbo, and CI exist; `uv` is not configured and Python tooling is Poetry-based. |
| 2 | Create top-level folder structure | Scaffold-complete | The repo shape broadly matches the documented structure. |
| 3 | Configure root CI pipeline for build/lint/test | Partial | CI exists, but `lint` and `test` are allowed to fail and typecheck/schema checks are missing. |
| 4 | Create extension MV3 manifest with host restriction | Scaffold-complete | MV3 manifest exists with host restriction to `https://www.incometax.gov.in/*`. |
| 5 | Build extension side panel shell UI | Scaffold-complete | Side panel app and panes exist, but state is still sample-driven. |
| 6 | Add extension background service worker and router | Scaffold-complete | Service worker, router, auth, connector, and action-runner modules exist. |
| 7 | Add extension backend connector over WebSocket | Partial | Connector hardcodes localhost WS and lacks auth, reconnect, and session binding. |
| 8 | Add extension secure storage helpers | Partial | Storage helpers exist, but "encryption" is only base64 encoding. |
| 9 | Add extension content script bootstrapping | Scaffold-complete | Content script entry exists and sends a page-detected event. |
| 10 | Add extension page detector | Partial | Detection is simple title/URL matching and supports only a subset of planned behavior. |
| 11 | Add extension field-map and action executors | Partial | Minimal DOM helpers exist, but no robust field schema extraction or tab-scoped execution layer. |
| 12 | Create backend FastAPI app and health endpoint | Scaffold-complete | App factory and `/health` endpoint exist. |
| 13 | Implement backend auth API stub | Scaffold-complete | Auth endpoint exists, but only returns a dev token. |
| 14 | Implement backend threads API stub | Scaffold-complete | Start/get endpoints exist, but pause/resume and true checkpoint lifecycle do not. |
| 15 | Implement backend documents signed-upload stub | Scaffold-complete | Signed-upload stub exists, but no storage integration or document state machine. |
| 16 | Implement backend actions decision API stub | Scaffold-complete | Approve/reject stub exists, but it is not persisted or wired end to end. |
| 17 | Implement backend tax-facts read API stub | Scaffold-complete | Read stub exists, but it returns placeholder data. |
| 18 | Implement backend websocket echo channel | Scaffold-complete | Websocket endpoint exists and echoes messages. |
| 19 | Implement LangGraph-style graph flow | Partial | A sequential custom runner exists, but not a real LangGraph state graph with branching/checkpoint semantics. |
| 20 | Implement checkpointer baseline | Partial | Checkpointer exists, but is in-memory only rather than Postgres-backed. |
| 21 | Add telemetry baseline | Partial | Tracing, metrics, analytics, and drift telemetry exist, but coverage and integrations are limited. |
| 22 | Add security baseline | Partial | Rate limiting, anomaly detection, and PII redaction exist, but consent, crypto, retention, and anti-phishing are incomplete. |
| 23 | Add DB layer baseline | Partial | One minimal migration and dataclass-like models exist, far short of the documented data model. |
| 24 | Implement workers queue and doc pipeline stages | Partial | Queue and pipeline stages exist, but most stages are pass-through stubs. |
| 25 | Implement workers parser modules | Partial | Parser files exist for many formats, but sampled parsers are all stub implementations. |
| 26 | Implement workers reconciliation and severity modules | Partial | Reconciliation helpers exist, but they are simplistic and not domain-complete. |
| 27 | Implement canonical tax-schema package | Partial | Shared schema package exists, but covers only a narrow subset of planned entities. |
| 28 | Implement action-dsl package | Partial | DSL spec/schema/dist exist, but bindings are narrow and only partly mirrored across TS/Py. |
| 29 | Implement portal-adapters package | Partial | Adapter files exist, but registry coverage is incomplete and `getFormSchema` returns empty arrays. |
| 30 | Implement deterministic rules-core and baseline tests | Partial | Rules-core exists, but rule coverage is narrow and automated tests are minimal. |

Summary for the 30-point plan:

- Scaffold-complete: 12
- Partial: 18
- Missing: 0

Important caveat: even the scaffold-complete items do not imply phase-exit completeness.

## Use-Case Coverage Matrix

Strict scoring rule used here:

- Partial means the repo contains some logic or UI toward the use case, but the documented outcome is not yet delivered end to end.
- Missing means the documented outcome is not meaningfully implemented.

Summary:

- Covered end to end: 0
- Partial: 48
- Missing: 22

### A. Onboarding And Session

1. Partial - Install and activate: MV3 manifest, host restriction, side panel, and chat shell exist, but there is no verified-host badge.
2. Missing - Device + session binding: auth is a dev-token stub with no device-scoped binding or revocation.
3. Missing - Consent-first onboarding: no onboarding flow or persisted `consents` ledger exists.
4. Missing - Resume a paused filing: checkpointer is in-memory only and there is no pause/resume flow or cross-session reload.

### B. Portal Awareness

5. Partial - Explain the current page: explanation node exists for many pages, but page detection is coarse.
6. Partial - List required inputs for this page: static lists exist, but they are not derived from real page adapters or DOM schemas.
7. Missing - Translate a portal validation error: errors are surfaced, but not rewritten into a targeted recovery question.
8. Partial - Identify the right ITR form: ITR inference exists, but the rule set is narrow and rationale is limited.
9. Partial - Flag an unsupported flow: some signals like foreign assets exist, but there is no true guided-mode downgrade or CA handoff.
10. Partial - Anti-phishing guard: host permissions are tight, but there is no verified-host badge, lookalike warning, or redirect suspension in the extension.

### C. Document Intake And Extraction

11. Partial - Parse AIS JSON/CSV/PDF: parser files exist, but current parser implementations are stubs.
12. Partial - Parse TIS: parser exists, but implementation is stubbed.
13. Partial - Parse Form 16: parser exists, but implementation is stubbed.
14. Partial - Parse Form 16A: parser exists, but implementation is stubbed.
15. Partial - Parse salary slips: parser exists, but implementation is stubbed.
16. Partial - Parse interest certificates: parser exists, but implementation is stubbed.
17. Partial - Parse rent receipts for HRA: parser exists, but implementation is stubbed and no HRA computation is wired.
18. Partial - Parse home-loan interest certificate: parser exists, but implementation is stubbed.
19. Partial - Parse ELSS/PPF/LIC/tuition receipts: `elss_ppf` parser exists, but implementation is stubbed and coverage is incomplete.
20. Missing - Parse health-insurance receipts: there is no dedicated health-insurance parser.
21. Partial - Parse broker capital-gains statements: parser exists, but implementation is stubbed.
22. Partial - OCR fallback on scanned proofs: OCR stage exists, but it is a pass-through stub.
23. Partial - Reject malicious or unreadable files: sanitize/virus-scan helpers exist, but they are minimal and not tied to a real upload pipeline.
24. Missing - Multi-version documents: document versioning is not implemented in code.

### D. Reconciliation And Mismatch Handling

25. Partial - AIS vs Form 16 salary diff: reconciliation exists in generic form, but not as a robust salary-specific flow.
26. Partial - AIS vs broker statement diff: reconciliation/duplicate modules exist, but no real capital-gains-specific matching logic is implemented.
27. Partial - AIS vs bank certificate interest diff: generic mismatch handling exists, but not a real interest-certificate reconciliation workflow.
28. Partial - Detect likely under-reporting: severity buckets include under-reporting, but logic is simplistic.
29. Partial - Detect likely AIS prefill issue: severity includes `prefill_issue`, but no evidence-backed override workflow exists.
30. Partial - Duplicate-proof detection: duplicate helpers exist, but only as trivial exact-match de-duplication.

### E. Tax Reasoning

31. Partial - Old vs new regime comparison: rules-core compares two numbers, but there is no full recommendation engine tied to complete facts.
32. Partial - Eligibility check for ITR-1: a narrow eligibility helper exists, but not the full pass/fail reason list.
33. Partial - Required-schedule detection: schedule helper exists, but only covers a few heads.
34. Partial - Deduction caps: 80C and 80D are present, but 80G, 80TTA, and 80TTB are missing.
35. Partial - Standard deduction applicability: standard deduction exists, but broader salary/pension handling is not integrated end to end.
36. Partial - Presumptive income eligibility: a minimal ITR-4 helper exists, but 44AD/44ADA reasoning is not implemented.
37. Partial - Residential-status questionnaire: there is a static question, but no day-count or tie-breaker rule engine.
38. Partial - Refund or additional-tax estimate: submission-summary code computes refund/payable, but it is not backed by a completed canonical-facts pipeline.

### F. Filling The Portal

39. Partial - Batched fill plan: fill-plan generation exists, but it is not backed by non-empty adapter schemas or full UI wiring.
40. Missing - Targeted single-field fill: the approval model includes the concept, but a true one-field flow is not wired.
41. Partial - Read-after-write: execution records a simulated readback, not a real DOM verification pass.
42. Partial - Selector-drift recovery: recovery flow and learned mappings exist, but persistence and actual retry execution are incomplete.
43. Missing - Regime toggle with impact preview: no dedicated regime-switch preview flow exists.
44. Partial - Bank account update with hard approval gate: generic approval exists, but there is no bank-change-specific gate or special handling.
45. Partial - Inline evidence on every field: evidence UI exists, but not as a per-filled-portal-field inline traceability flow.
46. Missing - Undo last fill batch: undo is not implemented.

### G. Review, Submission, Verification

47. Partial - Pre-submission summary: a strong summary node exists, but it is not validated against the real portal or durable artifacts.
48. Partial - Explicit submission consent: consent text and approval hashing exist, but there is no persisted `consents` ledger.
49. Partial - E-verification handoff: method guidance exists, but the full post-submit flow is not integrated end to end.
50. Missing - ITR-V + JSON archive: archive node only marks the thread archived; no ITR-V bundle exists.
51. Partial - Revised return: branch support exists, but the full workflow and data lineage are incomplete.
52. Missing - Updated return (ITR-U) support: not implemented.

### H. Post-Filing And Multi-Year

53. Missing - Year-over-year comparison: not implemented.
54. Missing - Next-AY readiness checklist: not implemented.
55. Missing - Notice-response prep: not implemented.
56. Missing - Refund status tracking: not implemented.

### I. CA Or Reviewer Workspace

57. Partial - Multi-client list: CA API can enumerate thread summaries, but there is no real dashboard workflow.
58. Missing - Reviewer sign-off: no dual-approval or reviewer authorization flow exists.
59. Missing - Bulk export: not implemented.

### J. Compliance, Safety, Trust

60. Partial - Action-level audit export: approval/execution metadata exists in memory, but there is no durable audit export pipeline.
61. Missing - Consent revocation: not implemented.
62. Missing - Retention-driven purge: not implemented.
63. Partial - PII-redacted logs: redaction helpers exist, but storage discipline is not enforced end to end.
64. Partial - Anomaly blocking: anomalies are detected and exposed, but threads are not auto-paused/quarantined.
65. Missing - Prompt-injection defense in documents: the safety rule is documented, but not enforced in code.

### K. Developer And Operability

66. Partial - Replay a failed filing: replay harness API exists, but it is in-memory and selector-based only.
67. Missing - Adapter hot-swap: not implemented.
68. Partial - Rule-version pinning: version fields exist in places, but real version pinning and replay fidelity are incomplete.
69. Partial - Synthetic persona fixtures: several personas and synthetic-doc generators exist, but not the planned 50+ regression-grade fixture bank.
70. Missing - Extraction-accuracy dashboards: analytics exist, but not parser/doc-type accuracy dashboards.

## Missing Implementation Inventory

This section consolidates what is still missing from the repo into implementation-level gaps.

### 1. Runtime Persistence And State

- Postgres-backed checkpoint storage.
- True pause/resume thread lifecycle.
- Persistent browser-session and portal-session state.
- Durable thread history and replay metadata.

### 2. Data Model Realization

- SQLAlchemy or equivalent models for users, devices, sessions, documents, facts, approvals, consents, portal mappings, and artifacts.
- Migrations beyond the single `filing_audit_trail` bootstrap table.
- Row-level access rules and durable audit writes.

### 3. Auth, Consent, And Security

- Device binding and token refresh/revocation.
- Persisted consent ledger with revoke flows.
- Retention/purge jobs.
- Real cryptography for extension session data.
- Verified-host badge, anti-phishing banner, and redirect suspension.
- Stronger anomaly response than header annotation.

### 4. Portal Understanding

- Registry wiring for all page adapters.
- Real `getFormSchema` results for every supported page.
- Rich DOM-driven page detection instead of title-only heuristics.
- Validation-error translation into user-actionable guidance.
- Selector snapshot tests for each adapter.

### 5. Document Pipeline

- Real signed-upload flow to object storage.
- Queue-backed worker orchestration.
- Real text extraction, table extraction, and OCR fallback.
- Non-stub parsers for AIS/TIS/Form16/Form16A/salary slips/interest certificates/rent receipts/home-loan certificates/ELSS-PPF proofs/health-insurance receipts/broker statements.
- Document versioning.

### 6. Canonical Facts And Evidence

- Normalization of parser output strictly into `packages/tax-schema`.
- Evidence pointer persistence for every fact.
- Extractor-version and rule-version persistence per fact.
- Better tax-schema coverage for capital gains, house property, other sources, tax paid, approvals, evidence, and artifacts.

### 7. Reconciliation And Rules

- Real AIS-vs-doc reconciliation logic by document type.
- Duplicate-trade and duplicate-proof detection.
- Broader mismatch severity logic.
- Deduction caps beyond 80C/80D.
- Residential-status computation.
- Schedule detection and disclosure checks for more flows.
- Presumptive-taxation rules.

### 8. Browser Execution And Audit

- Backend-to-extension action dispatch bound to the correct tax-portal tab.
- Real single-field and batched fill flows.
- Actual read-after-write verification.
- Undo-last-batch where portal behavior allows it.
- Special approval flows for regime changes and bank-account changes.
- Durable action-level audit export.

### 9. Submission And Post-Filing

- Artifact archive: ITR-V, evidence bundle, JSON export.
- Updated return (ITR-U) support.
- Year-over-year comparison.
- Readiness checklist for next AY.
- Notice-response explainer.
- Refund-status tracking.

### 10. CA Workspace And Review Flow

- Actual reviewer dashboard UI.
- Reviewer sign-off and client counter-consent.
- Bulk export for clients.

### 11. Testing, CI, And Operability

- Backend unit tests.
- Worker tests.
- Extension tests.
- Playwright scenarios, not just config.
- Adapter snapshot tests.
- Persona-driven end-to-end replay coverage.
- CI without `|| true` masking.
- Installed dependency/toolchain path for local and CI runs.
- Extraction-accuracy dashboards.

## Recommended 30-Point Implementation Plan

This plan replaces the current optimistic "Executed" interpretation with an implementation sequence aimed at actually closing the documented gaps.

1. Reclassify `docs/IMPLEMENTATION_30_POINT_PLAN.md` so it no longer marks scaffold-only work as done.
2. Make CI a real quality gate: install dependencies, run build/lint/typecheck/test without `|| true`, and fail on red.
3. Add backend unit tests for core agent nodes, APIs, and security helpers.
4. Add worker tests for parsers, normalization, and reconciliation.
5. Add extension tests for page detection, action execution, and side panel state flow.
6. Replace the in-memory checkpointer with a Postgres-backed checkpoint store.
7. Implement pause, resume, and thread-history APIs on top of durable checkpoints.
8. Expand the real database schema to cover users, devices, browser sessions, portal sessions, documents, facts, approvals, consents, portal mappings, and artifacts.
9. Build actual auth with device binding, refresh tokens, revocation, and session metadata.
10. Implement a real consent service with purpose-specific grants, revocation, and purge-job enqueueing.
11. Replace extension base64 storage with real WebCrypto-based wrapping for session data.
12. Add verified-host UI, anti-phishing banners, and redirect suspension behavior in the extension.
13. Register all supported page adapters in `packages/portal-adapters` and remove the current title-only dependence.
14. Implement non-empty `getFormSchema` and real validation readers for every supported page adapter.
15. Add adapter snapshot tests for dashboard, start filing, ITR selection, personal info, salary, deductions, tax paid, bank, regime, summary, capital gains, house property, and e-verify.
16. Implement the real signed-upload flow, document metadata persistence, and storage keys.
17. Wire backend document intake to a real worker queue instead of pass-through stubs.
18. Implement text extraction, table extraction, and OCR fallback with confidence capture.
19. Replace every parser stub with typed extraction for AIS JSON, AIS CSV, AIS PDF, TIS, Form 16, Form 16A, salary slips, interest certificates, rent receipts, home-loan certificates, ELSS-PPF proofs, health-insurance receipts, and broker capital-gains statements.
20. Normalize all parser output strictly into `packages/tax-schema` and reject free-form fact shapes.
21. Persist evidence pointers, extractor versions, rule versions, and document-version history for every fact.
22. Implement real AIS-vs-doc reconciliation, mismatch severity, duplicate detection, and targeted follow-up questions.
23. Expand `packages/rules-core` for ITR eligibility, residential-status rules, deduction caps, presumptive taxation, schedule detection, and disclosure checks.
24. Expand `packages/tax-schema` for capital gains, house property, other sources, tax paid, evidence, approvals, and submission artifacts.
25. Rebuild fill-plan generation on top of real adapter schemas and evidence confidence rather than static field maps alone.
26. Wire backend-approved actions to the extension so fills happen on the bound portal tab, with real read-after-write verification.
27. Add selector-drift learning persistence, retry execution, and undo-last-batch support where the portal permits it.
28. Implement special approvals for bank-account changes, regime switches, draft save, submit, and e-verify handoff, and write them durably to audit storage.
29. Finish submission/post-filing flows: ITR-V generation, evidence bundle archive, offline JSON export validation, revised-return polishing, and ITR-U gating.
30. Build the CA workspace, persona-driven replay suite, extraction-accuracy dashboards, and nightly drift-autopilot loop so the system can be operated and improved safely.

## Practical Conclusion

The project is not empty. It contains a real and useful scaffold, especially in backend orchestration and UI structure.

But it is not yet accurate to say that the plan has been fully implemented or that the documented use cases are comprehensively covered.

The most accurate description is:

- broad scaffold present;
- selected core flows partially implemented;
- major production, compliance, parser, persistence, adapter, and test gaps still open.