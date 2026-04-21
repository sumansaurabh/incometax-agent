# Plan And Use-Case Coverage Audit

Date: 2026-04-22

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
- Post-filing runtime for year-over-year comparison, next-AY readiness checklists, read-only notice-response preparation, and refund-status capture with persisted filing-state records and sidepanel UI.
- CA workspace export bundles for single-client and multi-client archives, including stored filing artifacts and prepared handoff packages.
- Official filing-artifact attachment that replaces the placeholder ITR-V archive with captured portal acknowledgement content when the user provides or captures it.

Validation performed after these implementations:

- `PYTHONPATH=apps/backend/src:apps/workers/src ITX_DATABASE_URL=postgresql://itx:itx@localhost:5432/itx python -m pytest apps/backend/tests/api/test_actions.py apps/backend/tests/api/test_filing.py` passed.
- `PYTHONPATH=apps/backend/src:apps/workers/src python -m compileall apps/backend/src apps/workers/src` passed.
- `pnpm --filter @itx/extension typecheck` passed.
- `PYTHONPATH=apps/backend/src:apps/workers/src:packages/rules-core/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest apps/backend/tests/api/test_review_workspace.py` passed.
- `python -m compileall apps/backend/src apps/workers/src` passed after the new support-assessment, quarantine, and document-security changes.
- `pnpm --filter @itx/extension build` passed after wiring validation help, regime preview, support-status, handoff, and quarantine UI.
- `ITX_DATABASE_URL=postgresql://itx:itx@localhost:5432/itx PYTHONPATH=apps/backend/src:apps/workers/src:packages/rules-core/src python -m pytest apps/backend/tests/api/test_filing.py -q` passed after the post-filing implementation.
- `PYTHONPATH=apps/backend/src:apps/workers/src:packages/rules-core/src python -m compileall apps/backend/src apps/workers/src packages/rules-core/src` passed after the post-filing implementation and Python 3.9 annotation cleanup.
- `ITX_DATABASE_URL=postgresql://itx:itx@localhost:5432/itx PYTHONPATH=apps/backend/src:apps/workers/src:packages/rules-core/src python -m pytest apps/backend/tests/api/test_filing.py apps/backend/tests/api/test_reviewer_workflow.py -q` passed after adding CA export bundles.

What is still materially pending now is concentrated in the remaining Phase 0 and Phase 1 hardening gaps, the Phase 4 updated-return and dashboard-depth gaps, and the Phase 5 breadth and operability backlog. `docs/IMPLEMENTATION_30_POINT_PLAN.md` now holds the canonical 30-point finish plan for that remaining work.

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

- Backend graph and checkpoint runtime: `apps/backend/src/itx_backend/agent/graph.py`, `apps/backend/src/itx_backend/agent/checkpointer.py`
- Durable action and filing runtime: `apps/backend/src/itx_backend/services/action_runtime.py`, `apps/backend/src/itx_backend/services/filing_runtime.py`
- Auth, security, and CA workspace APIs: `apps/backend/src/itx_backend/api/auth.py`, `apps/backend/src/itx_backend/api/security.py`, `apps/backend/src/itx_backend/api/ca_workspace.py`
- Extension sidepanel and authenticated session bridge: `apps/extension/src/sidepanel/App.tsx`, `apps/extension/src/shared/auth-session.ts`, `apps/extension/src/background/connector.ts`
- Document pipeline, sanitizer, and support workflow runtime: `apps/backend/src/itx_backend/api/documents.py`, `apps/workers/src/itx_workers/security/sanitize.py`, `apps/backend/src/itx_backend/services/review_workspace.py`
- Adapter coverage gaps: `packages/portal-adapters/src/pages/*.ts`
- CI masking failures: `.github/workflows/ci.yml`
- Remaining automated test and persona coverage: `apps/backend/tests/`, `tests/fixtures/`, `tests/personas/`

## Executive Summary

The repository is no longer just a scaffold, but it is still short of phase-exit completeness.

The strongest areas are:

- async Postgres-backed backend runtime for documents, proposals, approvals, executions, submissions, consents, purge jobs, and revisions;
- authenticated extension flows for validation help, regime preview, support assessment, CA handoffs, quarantine resume, and reviewer sign-off;
- reviewer-facing export bundles that package client state, filing artifacts, and handoff packages for downstream operations;
- document intake, normalization, evidence persistence, and reconciliation baseline;
- trust and safety controls including verified-host states, prompt-injection screening, anomaly quarantine, and durable audit records.

The weakest areas are now:

- page adapters and DOM-derived schemas across more portal branches;
- broader parser coverage, OCR quality, and extraction accuracy validation;
- broader rules coverage for complex taxpayers and updated-return coverage;
- deeper CA dashboard tooling, richer analytics, replay depth, and inline field evidence;
- automated tests and CI enforcement.

Bottom line:

- Phase 2-4 core assisted filing is implemented in code with durable persistence.
- Several Phase 5 trust/safety items are now also implemented in code.
- The repository still falls short of full roadmap completion because broader taxpayer coverage, updated-return coverage, CA dashboard depth, and CI depth remain open.

## Phase-Level Verdict

| Phase | Verdict | Why |
|---|---|---|
| Phase 0 - Foundations | Partial | Monorepo, backend, extension, CI, and shared packages exist, and checkpoint persistence is now Postgres-backed, but CI/auth/security hardening is still thin. |
| Phase 1 - Portal Copilot | Partial | Page detection, explanation, and evidence UI exist, but adapters return empty schemas and detection is mostly title/URL based. |
| Phase 2 - Document Intelligence | Implemented-in-code | Postgres-backed documents, storage, queueing, extraction, normalization, evidence persistence, and reconciliation are implemented; broader fixture-bank accuracy gates remain to be expanded. |
| Phase 3 - Guided Autofill | Implemented-in-code | Durable proposal/approval/execution persistence, live sidepanel approvals, browser execution/readback, and undo are implemented and validated in tests/typecheck. |
| Phase 4 - Completion Flow | Implemented-in-code | Submission summary, consent ledger, artifact archive, e-verification handoff, and revision branching now have persistence, APIs, and sidepanel flow; live demo-account exit criteria remain unverified. |
| Phase 5 - Scale And Hardening | Partial | Replay, drift telemetry, offline export, retention purge, trust boundaries, validation-help, unsupported-flow downgrade, prompt-injection screening, anomaly quarantine, and reviewer sign-off flows exist; dashboards, bulk workspace operations, and broader operational hardening remain incomplete. |

## Exit-Criteria Check

`docs/PLAN.md` defines phase exit criteria. None of them are met yet.

Key reasons:

- Extension-to-backend round trip exists, but not as a verified, authenticated, production flow.
- Checkpoints are now persisted in Postgres, but CI quality gates and production auth still lag behind the roadmap.
- CI is not a real quality gate because lint/test are allowed to fail.
- Parser accuracy, replay coverage, persona flows, and live demo validations are not present.
- Submission artifacts, approvals, consents, and filing-runtime records are now durably written for the implemented path, but broader audit export, retention, and operational controls remain incomplete.

## 30-Point Finish Plan

`docs/IMPLEMENTATION_30_POINT_PLAN.md` is now the canonical remaining-work plan. The earlier scaffold-executed checklist has been retired because it no longer matches the current repo state.

| Workstream | Items | Primary phase gaps it closes |
|---|---|---|
| Foundation and trust | 1-5 | Remaining Phase 0 hardening, consent-first UX, CI gates, environment bootstrap, audit export |
| Portal awareness and adapters | 6-10 | Remaining Phase 1 adapter depth, page detection, validation recovery, selector-drift recovery |
| Document intelligence quality | 11-15 | Phase 2 parser breadth, OCR quality, fixture-bank accuracy, reconciliation depth |
| Rules, reasoning, and autofill breadth | 16-20 | Phase 3 rule coverage, persona coverage, inline evidence, tested autofill reliability |
| Filing, reviewer, and post-filing completion | 21-25 | Remaining Phase 4 artifact, reviewer workspace, and post-filing gaps |
| Reliability, analytics, and operations | 26-30 | Phase 5 replay, drift automation, analytics, security operations, and exit validation |

The plan is intentionally cross-phase rather than phase-siloed.

- Items 1-10 close the remaining Phase 0 and Phase 1 gaps.
- Items 11-20 deepen the already-implemented Phase 2 and Phase 3 core into broader supported coverage.
- Items 21-25 close the remaining Phase 4 and post-filing/operator workflow gaps.
- Items 26-30 close the remaining Phase 5 operability gaps and produce the final exit evidence.

## Use-Case Coverage Matrix

Strict scoring rule used here:

- Implemented-in-code means the repo contains a durable code path for the use case, with persistence and/or validation, but live-account, production-hardening, or UX-polish criteria may still remain.
- Partial means the repo contains some logic, UI, or schema support toward the use case, but the documented outcome is not yet delivered end to end.
- Missing means the documented outcome is not meaningfully implemented.

Summary:

- Implemented-in-code: 25
- Partial: 42
- Missing: 3

### A. Onboarding And Session

1. Partial - Install and activate: MV3 manifest, host restriction, side panel, and verified/lookalike host trust state are in place, but onboarding and trust-recovery UX are still incomplete.
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
50. Implemented-in-code - ITR-V + JSON archive: summary, offline JSON, and evidence bundle are archived, and the placeholder ITR-V can now be replaced with an attached official portal acknowledgement artifact.
51. Implemented-in-code - Revised return: thread branching, lineage persistence, and sidepanel-triggered revision flow are implemented.
52. Missing - Updated return (ITR-U) support: not implemented.

### H. Post-Filing And Multi-Year

53. Implemented-in-code - Year-over-year comparison: filing-state comparisons are generated from current and prior filed summaries, persisted, and surfaced in the sidepanel.
54. Implemented-in-code - Next-AY readiness checklist: the backend generates a persisted next-assessment-year checklist from filing facts and surfaced filing outcomes.
55. Implemented-in-code - Notice-response prep: the backend prepares a read-only notice summary from pasted notice text, extracts adjustments and timelines, and packages suggested supporting documents without submitting a response.
56. Implemented-in-code - Refund status tracking: refund status can be captured from the portal page or manual entry, persisted, and surfaced as part of filing state.

### I. CA Or Reviewer Workspace

57. Partial - Multi-client list: CA API can enumerate thread summaries, but there is no real dashboard workflow.
58. Implemented-in-code - Reviewer sign-off: owners can request reviewer sign-off for an approval, reviewers gain scoped access to the shared thread, reviewer decisions are persisted, and execution stays blocked until client counter-consent is recorded.
59. Implemented-in-code - Bulk export: CA users can now download single-client or multi-client ZIP archives containing client summaries, stored filing artifacts, and prepared handoff packages.

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

- Strengthen extension-side cryptography beyond the current lightweight storage approach.
- Consent-first onboarding UX for upload/fill/regime-compare/reviewer-share purposes.
- Expand trust copy and guided recovery around verified, lookalike, and unsupported portal states.

### 2. Portal Awareness And Adapter Depth

- Finish non-empty adapter schemas for all supported pages.
- Move more detection/schema extraction away from title/URL heuristics and toward DOM-driven logic.
- Extend targeted validation guidance beyond the currently covered high-friction pages.
- Expand unsupported-flow downgrade coverage across more portal branches.

### 3. Document Intelligence Quality

- Broaden and harden parser coverage for TIS, salary slips, rent receipts, home-loan certificates, ELSS/PPF proofs, and broker statements.
- Improve OCR quality beyond the current lightweight fallback.
- Expand age-based and edge-case deduction handling, especially around 80D and richer deduction families.
- Raise parser accuracy with a larger validated fixture bank.

### 4. Rules And Reasoning Breadth

- Expand ITR eligibility, required-schedule detection, residential-status rules, deduction caps, and presumptive-taxation support.
- Improve disclosure checks and unsupported-case escalation coverage.

### 5. Browser Execution Hardening

- Persist selector retraining in a way that meaningfully survives portal drift.
- Improve adapter coverage so batched fills work across more real portal pages.
- Surface evidence inline against filled fields, not only in the sidepanel.
- Package action-level audit data into a downloadable export.

### 6. Filing And Post-Filing Completion

- Broaden the new official-artifact attachment path with stronger page-specific capture and portal-download automation when available.
- Add ITR-U support.
- Broaden the new post-filing baseline with uploaded-notice parsing, refund-status history, and response-packet export.

### 7. CA / Reviewer Workspace

- Build an actual reviewer dashboard UI on top of the current list/detail APIs.
- Broaden the new export baseline with queue filters, saved export presets, and dashboard-integrated packaging flows.

### 8. Compliance, Retention, And Security Response

- Package audit and purge evidence into operator-friendly exports and dashboards.
- Deepen anomaly investigation tooling beyond quarantine and manual resume.
- Expand document-security policy coverage and reviewer triage for medium-risk cases.

### 9. Testing, Analytics, And Operability

- Expand backend, worker, and extension automated tests.
- Add richer replay coverage tied to stored checkpoints and DOM snapshots.
- Add extraction-accuracy dashboards by document type and parser version.
- Strengthen CI quality gates so failing lint/test paths cannot be masked.

## Recommended Remaining Implementation Plan

Use `docs/IMPLEMENTATION_30_POINT_PLAN.md` as the canonical remaining-work plan.

If this needs to be broken into delivery tracks, use these six workstreams rather than maintaining a second checklist here:

1. Foundation and trust hardening.
2. Portal awareness and adapter depth.
3. Document intelligence quality.
4. Rules, reasoning, and autofill breadth.
5. Filing, reviewer, and post-filing completion.
6. Reliability, analytics, and operations.

## Practical Conclusion

The project is no longer just a scaffold.

It now has a meaningful implemented-in-code core across document ingestion, guided autofill, and filing completion. But it is still not accurate to say that all documented use cases are covered.

The most accurate description is:

- a solid Phase 2-4 assisted-filing path exists in code;
- many supporting and Phase 5 use cases are still only partial;
- post-filing features, richer reviewer workspace UX, and broader quality hardening remain open.