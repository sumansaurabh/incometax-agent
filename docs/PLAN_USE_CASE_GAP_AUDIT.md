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
- Device-bound auth/session lifecycle, authenticated API + WebSocket access, consent revocation, retention-driven purge jobs, and verified-host / lookalike-domain protection in the extension.
- Validation-error translation, regime comparison with targeted regime-switch proposals, unsupported-flow assessment with guided-checklist downgrade, durable CA handoff packages, and thread quarantine on anomaly detection.
- Prompt-injection-aware document screening that flags risky uploads and blocks high-risk text documents before fact extraction.

Validation performed after these implementations:

- `PYTHONPATH=apps/backend/src:apps/workers/src ITX_DATABASE_URL=postgresql://itx:itx@localhost:5432/itx python -m pytest apps/backend/tests/api/test_actions.py apps/backend/tests/api/test_filing.py` passed.
- `PYTHONPATH=apps/backend/src:apps/workers/src python -m compileall apps/backend/src apps/workers/src` passed.
- `pnpm --filter @itx/extension typecheck` passed.
- `PYTHONPATH=apps/backend/src:apps/workers/src:packages/rules-core/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest apps/backend/tests/api/test_review_workspace.py` passed.
- `python -m compileall apps/backend/src apps/workers/src` passed after the new support-assessment, quarantine, and document-security changes.
- `pnpm --filter @itx/extension build` passed after wiring validation help, regime preview, support-status, handoff, and quarantine UI.

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

The weakest areas are now:

- real document upload, parsing, normalization, and evidence persistence;
- page adapters and DOM schemas for the portal;
- broader parser coverage, reviewer workflows, and post-filing features;
- deeper CA workspace tooling, richer analytics, and inline field evidence;
- automated tests and CI enforcement.

Bottom line:

- Phase 2-4 core assisted filing is implemented in code with durable persistence.
- Several Phase 5 trust/safety items are now also implemented in code.
- The repository still falls short of full roadmap completion because reviewer workflows, broader taxpayer coverage, post-filing features, and CI depth remain open.

## Phase-Level Verdict

| Phase | Verdict | Why |
|---|---|---|
| Phase 0 - Foundations | Partial | Monorepo, backend, extension, CI, and shared packages exist, and checkpoint persistence is now Postgres-backed, but CI/auth/security hardening is still thin. |
| Phase 1 - Portal Copilot | Partial | Page detection, explanation, and evidence UI exist, but adapters return empty schemas and detection is mostly title/URL based. |
| Phase 2 - Document Intelligence | Implemented-in-code | Postgres-backed documents, storage, queueing, extraction, normalization, evidence persistence, and reconciliation are implemented; broader fixture-bank accuracy gates remain to be expanded. |
| Phase 3 - Guided Autofill | Implemented-in-code | Durable proposal/approval/execution persistence, live sidepanel approvals, browser execution/readback, and undo are implemented and validated in tests/typecheck. |
| Phase 4 - Completion Flow | Implemented-in-code | Submission summary, consent ledger, artifact archive, e-verification handoff, and revision branching now have persistence, APIs, and sidepanel flow; live demo-account exit criteria remain unverified. |
| Phase 5 - Scale And Hardening | Partial | Replay, drift telemetry, offline export, retention purge, trust boundaries, validation-help, unsupported-flow downgrade, prompt-injection screening, and anomaly quarantine exist; reviewer workflow depth, dashboards, and broader operational hardening remain incomplete. |

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

- Implemented-in-code means the repo contains a durable code path for the use case, with persistence and/or validation, but live-account, production-hardening, or UX-polish criteria may still remain.
- Partial means the repo contains some logic, UI, or schema support toward the use case, but the documented outcome is not yet delivered end to end.
- Missing means the documented outcome is not meaningfully implemented.

Summary:

- Implemented-in-code: 18
- Partial: 43
- Missing: 9

### A. Onboarding And Session

1. Partial - Install and activate: MV3 manifest, host restriction, and side panel are in place, but there is no verified-host badge.
2. Implemented-in-code - Device + session binding: device-bound login, refresh, revocation, request auth context, and authenticated WebSocket binding are implemented.
3. Partial - Consent-first onboarding: a `consents` ledger now exists for submit/e-verify approvals, but there is no explicit onboarding or purpose-by-purpose consent-first flow.
4. Partial - Resume a paused filing: checkpoints are now stored in Postgres and thread IDs can be reloaded, but explicit pause/resume UX and full browser-session restoration are still incomplete.

### B. Portal Awareness

5. Partial - Explain the current page: explanation node exists for many pages, but page detection is still coarse.
6. Partial - List required inputs for this page: static adapter schemas exist for many pages, but they are not fully DOM-derived and some pages still have empty schemas.
7. Implemented-in-code - Translate a portal validation error: validation errors are translated into plain-English recovery guidance and surfaced in the sidepanel.
8. Partial - Identify the right ITR form: ITR inference exists, but the rule set is narrow and rationale is limited.
9. Implemented-in-code - Flag an unsupported flow: the backend assesses unsupported/risky cases, downgrades the thread into guided-checklist mode, and can prepare a durable CA handoff package.
10. Implemented-in-code - Anti-phishing guard: the extension now shows verified/lookalike/unsupported trust state and suspends automation on suspicious or unsupported hosts.

### C. Document Intake And Extraction

11. Partial - Parse AIS JSON/CSV/PDF: parsers exist and feed normalized facts/evidence, but breadth and accuracy are still limited.
12. Partial - Parse TIS: parser exists, but remains heuristic and lightly validated.
13. Partial - Parse Form 16: core salary/TDS extraction exists, but full Part A + Part B richness is incomplete.
14. Partial - Parse Form 16A: TDS-on-other-income extraction exists, but coverage remains narrow.
15. Partial - Parse salary slips: parser exists, but robust month-by-month reconciliation is incomplete.
16. Partial - Parse interest certificates: parser exists, but broader institution and layout coverage is still limited.
17. Partial - Parse rent receipts for HRA: rent/HRA-related extraction exists, but a full HRA rules workflow and audit trail remain incomplete.
18. Partial - Parse home-loan interest certificate: interest/principal split exists, but schedule-ready completeness is limited.
19. Partial - Parse ELSS/PPF/LIC/tuition receipts: parser support exists, but the broader family of 80C proofs is still incomplete.
20. Partial - Parse health-insurance receipts: a dedicated parser exists, but age-based cap handling and edge cases are incomplete.
21. Partial - Parse broker capital-gains statements: parser exists, but lot-level and schedule-grade handling is incomplete.
22. Partial - OCR fallback on scanned proofs: OCR fallback runs and records confidence, but remains lightweight.
23. Partial - Reject malicious or unreadable files: signed upload, virus scan, and sanitization are wired into upload, but controls remain basic.
24. Implemented-in-code - Multi-version documents: re-uploads create and preserve `document_versions` history.

### D. Reconciliation And Mismatch Handling

25. Partial - AIS vs Form 16 salary diff: reconciliation exists in generic form, but not as a robust salary-specific flow.
26. Partial - AIS vs broker statement diff: reconciliation and duplicate modules exist, but no real capital-gains-specific matching logic is implemented.
27. Partial - AIS vs bank certificate interest diff: generic mismatch handling exists, but not a real interest-certificate reconciliation workflow.
28. Partial - Detect likely under-reporting: severity buckets include under-reporting, but logic is still simplistic.
29. Partial - Detect likely AIS prefill issue: mismatch severity and evidence UI exist, but no full override workflow exists.
30. Partial - Duplicate-proof detection: duplicate helpers exist, but only as simple heuristic de-duplication.

### E. Tax Reasoning

31. Partial - Old vs new regime comparison: regime math exists in the submission flow, but recommendation UX and broader rule completeness are limited.
32. Partial - Eligibility check for ITR-1: a narrow eligibility helper exists, but not the full pass/fail reason list.
33. Partial - Required-schedule detection: schedule helper exists, but only covers a few heads.
34. Partial - Deduction caps: 80C and 80D are present and some additional fields exist, but full cap coverage including 80TTB remains incomplete.
35. Partial - Standard deduction applicability: standard deduction exists, but broader salary/pension handling is not integrated end to end.
36. Partial - Presumptive income eligibility: a minimal ITR-4 helper exists, but 44AD/44ADA reasoning is not implemented.
37. Partial - Residential-status questionnaire: there is a static question, but no day-count or tie-breaker rule engine.
38. Partial - Refund or additional-tax estimate: submission summary computes refund/payable from normalized facts, but broader rules coverage is still incomplete.

### F. Filling The Portal

39. Partial - Batched fill plan: durable proposal and execution flows exist, but adapter/page coverage is still incomplete.
40. Implemented-in-code - Targeted single-field fill: proposal generation supports page and field targeting with focused approvals.
41. Implemented-in-code - Read-after-write: browser execution captures observed post-fill values and persists them.
42. Partial - Selector-drift recovery: recovery flow and learned mappings exist, but persistence and actual retry execution are incomplete.
43. Implemented-in-code - Regime toggle with impact preview: the backend compares old vs new regime, the sidepanel shows the delta, and a targeted regime-switch proposal can be prepared.
44. Implemented-in-code - Bank account update with hard approval gate: bank-related fills trigger a dedicated high-risk approval path and are audited.
45. Partial - Inline evidence on every field: evidence UI exists, but not as a per-filled-portal-field inline traceability flow.
46. Implemented-in-code - Undo last fill batch: undo API and sidepanel flow revert the latest fill batch.

### G. Review, Submission, Verification

47. Implemented-in-code - Pre-submission summary: summary generation, persistence, and sidepanel review flow are implemented.
48. Implemented-in-code - Explicit submission consent: consent text is hashed and persisted in `consents` for submit/e-verify approvals.
49. Implemented-in-code - E-verification handoff: method-specific handoff, manual completion tracking, and sidepanel flow are implemented.
50. Partial - ITR-V + JSON archive: summary, offline JSON, and evidence bundle are archived, but the ITR-V artifact is still a placeholder bundle rather than the official portal-issued file.
51. Implemented-in-code - Revised return: thread branching, lineage persistence, and sidepanel-triggered revision flow are implemented.
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

60. Partial - Action-level audit export: action and filing audit data are durably written, but there is no dedicated export packaging flow yet.
61. Implemented-in-code - Consent revocation: consents can be revoked and the purge workflow is queued and surfaced in the UI.
62. Implemented-in-code - Retention-driven purge: purge jobs delete stored artifacts, replay data, and checkpoint-linked material on schedule or immediate revocation.
63. Partial - PII-redacted logs: redaction helpers exist, but storage discipline is not enforced end to end.
64. Implemented-in-code - Anomaly blocking: anomaly headers now trigger thread quarantine, automation APIs reject quarantined work, and the sidepanel exposes explicit resume-after-review control.
65. Implemented-in-code - Prompt-injection defense in documents: text uploads are scanned for prompt-like control content, high-risk documents are blocked before extraction, and risky cases feed the support assessment.

### K. Developer And Operability

66. Partial - Replay a failed filing: replay harness API exists, but it is in-memory and selector-based only.
67. Missing - Adapter hot-swap: not implemented.
68. Partial - Rule-version pinning: version fields exist in places, but real version pinning and replay fidelity are incomplete.
69. Partial - Synthetic persona fixtures: several personas and synthetic-doc generators exist, but not the planned 50+ regression-grade fixture bank.
70. Missing - Extraction-accuracy dashboards: generic analytics exist, but not parser/doc-type accuracy dashboards.

## Current Pending Implementation Inventory

This section consolidates what is still genuinely pending after the recent Phase 2-4 implementation work.

### 1. Auth, Session, And Trust Boundaries

- Device-bound auth, refresh, revocation, and browser-session binding.
- Consent-first onboarding UX for upload/fill/regime-compare/reviewer-share purposes.
- Verified-host badge, lookalike-domain detection, and redirect suspension.
- Stronger extension-side cryptography than the current lightweight storage approach.

### 2. Portal Awareness And Adapter Depth

- Finish non-empty adapter schemas for all supported pages.
- Move more detection/schema extraction away from title/URL heuristics and toward DOM-driven logic.
- Translate portal validation errors into targeted recovery guidance.
- Add explicit unsupported-flow downgrade and CA handoff behavior.

### 3. Document Intelligence Quality

- Broaden and harden parser coverage for TIS, salary slips, rent receipts, home-loan certificates, ELSS/PPF proofs, and broker statements.
- Improve OCR quality beyond the current lightweight fallback.
- Expand age-based and edge-case deduction handling, especially around 80D and richer deduction families.
- Raise parser accuracy with a larger validated fixture bank.

### 4. Rules And Reasoning Breadth

- Expand ITR eligibility, required-schedule detection, residential-status rules, deduction caps, and presumptive-taxation support.
- Add regime-switch impact preview UX before committing changes.
- Improve disclosure checks and unsupported-case escalation coverage.

### 5. Browser Execution Hardening

- Persist selector retraining in a way that meaningfully survives portal drift.
- Improve adapter coverage so batched fills work across more real portal pages.
- Surface evidence inline against filled fields, not only in the sidepanel.
- Package action-level audit data into a downloadable export.

### 6. Filing And Post-Filing Completion

- Replace the placeholder ITR-V archive with the official portal-issued artifact when available.
- Add ITR-U support.
- Add year-over-year comparison, next-AY readiness, notice-response prep, and refund-status tracking.

### 7. CA / Reviewer Workspace

- Build an actual reviewer dashboard UI on top of the current list/detail APIs.
- Add reviewer sign-off, dual-approval, and client counter-consent.
- Add bulk export for clients.

### 8. Compliance, Retention, And Security Response

- Consent revocation flow using the existing schema support.
- Retention-driven purge of uploads and raw artifacts.
- Stronger anomaly response than passive observation.
- Real document prompt-injection defenses instead of minimal sanitization.

### 9. Testing, Analytics, And Operability

- Expand backend, worker, and extension automated tests.
- Add richer replay coverage tied to stored checkpoints and DOM snapshots.
- Add extraction-accuracy dashboards by document type and parser version.
- Strengthen CI quality gates so failing lint/test paths cannot be masked.

## Recommended Remaining Implementation Plan

This plan focuses only on the work that remains after the current Phase 2-4 implementation.

1. Replace the dev-token auth stub with device-bound auth, refresh, and revocation.
2. Add a consent-first onboarding flow for upload, fill, regime-compare, and reviewer-share purposes.
3. Add verified-host UI, lookalike-domain warnings, and redirect suspension in the extension.
4. Complete adapter schemas for all supported pages and remove remaining empty schemas.
5. Make page detection and required-input discovery more DOM-driven and less title/URL-dependent.
6. Translate portal validation errors into actionable recovery guidance.
7. Broaden parser coverage and accuracy for TIS, salary slips, rent receipts, home-loan certificates, ELSS/PPF proofs, and broker statements.
8. Improve OCR quality and validation coverage in the document pipeline.
9. Expand rules-core for residential status, richer deduction caps, fuller ITR eligibility, and presumptive-taxation reasoning.
10. Add regime-switch impact preview before the user approves a change.
11. Harden selector-drift recovery and persist learned mappings in an operationally useful way.
12. Add inline evidence traceability on filled portal fields.
13. Replace the placeholder ITR-V archive with the official filed artifact where available.
14. Implement ITR-U support with explicit escalation gates.
15. Add year-over-year comparison, next-AY readiness, notice-response prep, and refund-status tracking.
16. Build a real CA/reviewer dashboard UI.
17. Add reviewer sign-off, dual approval, and client counter-consent.
18. Add bulk export for CA/reviewer workflows.
19. Implement consent revocation and retention-driven purge jobs.
20. Strengthen anomaly response from passive detection to active pause/quarantine.
21. Add meaningful document prompt-injection defenses beyond null-byte stripping.
22. Expand backend, worker, extension, and replay-based automated tests.
23. Add extraction-accuracy dashboards by parser version and document type.
24. Remove remaining CI masking so lint, test, and replay regressions fail fast.

## Practical Conclusion

The project is no longer just a scaffold.

It now has a meaningful implemented-in-code core across document ingestion, guided autofill, and filing completion. But it is still not accurate to say that all documented use cases are covered.

The most accurate description is:

- a solid Phase 2-4 assisted-filing path exists in code;
- many supporting and Phase 5 use cases are still only partial;
- production auth, reviewer workflows, post-filing features, retention/revocation, and broader quality hardening remain open.