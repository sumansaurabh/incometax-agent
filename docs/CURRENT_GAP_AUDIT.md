# Current Gap Audit

Date: 2026-04-22

This is a verified repo-state audit based on the current code, tests, and docs. It is meant to answer one question clearly: what is actually complete, what is only partial, and what still blocks this project from being market-complete.

## Bottom Line

- The repository is not scaffold-only anymore. The core backend runtime, document pipeline, approval-driven autofill flow, filing flow, consent ledger, reviewer sign-off flow, and artifact export paths are implemented in code.
- The repository is not roadmap-complete. Phase 0 and Phase 1 hardening are still incomplete, and Phase 5 now has real operational primitives but is still well short of production-grade operations.
- The repository is not market-complete. It supports a narrow assisted-filing wedge, not the full Indian individual income-tax market and not a production-grade CA operations product.

## What Is Materially Implemented

### 1. Agent runtime and persistence

Verified in:

- `apps/backend/src/itx_backend/agent/graph.py`
- `apps/backend/src/itx_backend/agent/checkpointer.py`
- `apps/backend/src/itx_backend/agent/state.py`

What is real today:

- Multi-node LangGraph orchestration exists.
- Postgres-backed checkpoint persistence exists.
- Filing threads can move through document intake, reconciliation, fill planning, approval, execution, submission summary, e-verification handoff, and archive.

### 2. Document intake, parsing, and evidence

Verified in:

- `apps/workers/src/itx_workers/document_pipeline.py`
- `apps/workers/src/itx_workers/parsers/`
- `apps/backend/tests/api/test_documents.py`
- `apps/workers/tests/test_document_pipeline.py`

What is real today:

- The worker pipeline covers classify, extract text, extract tables, OCR fallback, parse, extract entities, and normalize.
- Parsers exist for AIS, TIS, Form 16, Form 16A, salary slips, interest certificates, rent receipts, home-loan certificates, health insurance, ELSS/PPF, and broker capital gains.
- Evidence is surfaced into the extension via fact evidence and an evidence viewer.

### 3. Approval-gated autofill and audit trail

Verified in:

- `apps/backend/src/itx_backend/services/action_runtime.py`
- `apps/backend/src/itx_backend/agent/nodes/execute_actions.py`
- `apps/backend/tests/api/test_actions.py`
- `apps/extension/src/sidepanel/App.tsx`

What is real today:

- Proposals, approvals, executions, undo, and read-after-write are implemented.
- High-risk actions such as bank changes are approval-gated.
- Reviewer sign-off and client counter-consent are wired into the execution path.

### 4. Filing completion, revision, and post-filing baseline

Verified in:

- `apps/backend/src/itx_backend/services/filing_runtime.py`
- `apps/backend/src/itx_backend/services/itr_u_service.py`
- `apps/backend/src/itx_backend/services/post_filing.py`
- `apps/backend/tests/api/test_filing.py`

What is real today:

- Submission summary persistence exists.
- Submit and e-verify consent capture exists.
- Filing artifacts, revision branching, and ITR-U baseline support exist.
- Post-filing refund snapshots and year-over-year style state handling exist.

### 5. Auth, trust, and reviewer workspace baseline

Verified in:

- `apps/backend/src/itx_backend/api/auth.py`
- `apps/backend/src/itx_backend/security/request_auth.py`
- `apps/backend/src/itx_backend/security/quarantine.py`
- `apps/backend/src/itx_backend/api/ca_workspace.py`
- `apps/extension/src/shared/auth-session.ts`
- `apps/extension/manifest.json`

What is real today:

- Device-bound auth and authenticated API access exist.
- Host restrictions and suspicious-host protection exist in the extension.
- Consent revocation and purge jobs exist.
- Reviewer sign-off, handoff packaging, and export APIs exist.

### 6. Consent-first onboarding, startup validation, and replay durability baseline

Verified in:

- `apps/backend/src/itx_backend/services/consent.py`
- `apps/backend/src/itx_backend/api/filing.py`
- `apps/backend/src/itx_backend/services/startup_health.py`
- `apps/backend/src/itx_backend/services/replay_harness.py`
- `apps/backend/src/itx_backend/api/replay.py`
- `apps/extension/src/sidepanel/App.tsx`
- `apps/extension/src/sidepanel/panes/ConsentOnboardingPane.tsx`
- `apps/backend/tests/api/test_replay.py`

What is real today:

- Purpose-specific onboarding consents exist and are required before sensitive guided actions proceed.
- Backend startup now validates database connectivity, document storage writability, and configuration sanity.
- The `/health` endpoint returns detailed check results instead of only a shallow liveness response.
- Replay snapshots and replay runs are now stored durably in Postgres rather than in process memory.
- Analytics event timelines and dashboard aggregates are now derived from durable Postgres-backed events rather than in-process lists.

## What Is Still Partial Or Missing

### 1. Portal adapters are the largest product gap

Verified in:

- `packages/portal-adapters/src/base.ts`
- `packages/portal-adapters/src/catalog.ts`
- `packages/portal-adapters/src/registry.ts`

Current state:

- The central adapter catalog now defines non-empty schemas, selector hints, aliases, text clues, and DOM signatures for the core supported filing pages.
- Adapter detection now uses thresholded weighted keyword, DOM-signature, text-clue, and resolved-selector scoring instead of first-match title or URL detection.
- Fixture-backed DOM tests now cover the core filing path: login, dashboard, file-return start, ITR selection, personal info, salary schedule, deductions, tax paid, bank account, summary review, and e-verify.
- Coverage is still too narrow for the full e-Filing surface, and drift recovery is still basic outside the core filing path.

Why it matters:

- Core guided autofill for a simple filing path is materially more usable than before.
- Broad autofill safety is still blocked by missing portal coverage beyond the main filing flow and by the lack of captured production DOM fixtures.
- This remains one of the biggest reasons the product is not market-ready.

### 2. Rules coverage is still narrow

Verified in:

- `packages/rules-core/src/rules_core/eligibility/itr1.py`
- `packages/rules-core/src/rules_core/schedules/required_schedules.py`
- `packages/rules-core/src/rules_core/caps/`
- `packages/rules-core/src/rules_core/regime/`

Current state:

- Rules coverage is no longer ITR-1-only.
- The engine now includes residential-status classification, broader ITR eligibility helpers, richer schedule detection, disclosure checks, HRA treatment, and additional Chapter VI-A caps including 80G, 80TTA, 80TTB, 80E, 80EE, 80EEA, and 80GG.
- The existing contract is preserved while returning a much richer rule-evaluation payload.

Still missing or too thin:

- More complete taxpayer coverage across complex capital gains, clubbing, business books, MAT/AMT, and edge-case disclosures.
- Deeper presumptive-tax and business-income reasoning beyond the current eligibility-level treatment.
- More exhaustive deduction, exemption, and validation coverage tied to real filing edge cases.

### 3. Parser breadth exists, but parser quality gates do not

Verified in:

- `apps/workers/src/itx_workers/parsers/`
- `apps/workers/tests/test_document_pipeline.py`
- `tests/personas/`

Current state:

- Parser count is good for this stage.
- A real regression bank now exists for the parser path, with fixture-backed scorecard coverage across the currently implemented parsers.
- The fixture bank is still synthetic and not yet representative of broad production document variation.

Evidence:

- The repo now includes a parser regression bank at `tests/fixtures/synthetic_docs/parser_regression_cases.json` plus a reusable scorecard runner at `scripts/parser_scorecard.py`.
- Eight top-level personas are present today: `salaried_simple`, `salaried_multi_employer`, `capital_gains_lite`, `mismatch_heavy`, `senior_citizen_interest`, `house_property_hra`, `presumptive_professional`, and `foreign_asset_review`.

Why it matters:

- There is now a real synthetic per-parser regression baseline.
- It is still hard to claim production extraction quality with confidence because the case bank is synthetic and still narrow.
- This is a direct blocker to calling the product production-ready.

### 4. Replay and analytics exist, but only as lightweight service layers

Verified in:

- `apps/backend/src/itx_backend/services/replay_harness.py`
- `apps/backend/src/itx_backend/api/replay.py`
- `apps/backend/src/itx_backend/services/analytics.py`
- `apps/backend/src/itx_backend/services/portal_drift_autopilot.py`

Current state:

- Replay snapshots and runs are now persisted in Postgres and covered by a backend API test.
- Analytics event timelines and dashboard totals are now persisted in Postgres and covered by a backend API test.
- Replay logic still only checks selector presence in captured HTML.
- Analytics remain coarse-grained and mostly event-log oriented rather than full operator observability.
- Drift autopilot groups failures and returns recommendations, but it is not a true nightly regeneration pipeline.

Why it matters:

- Durable replay is now a real reliability primitive.
- The operating model is still development-oriented because replay is not yet a full regression pipeline and analytics are still too shallow for production operations.

### 5. CA workspace is API-capable, but dashboard depth is not there yet

Verified in:

- `apps/backend/src/itx_backend/api/ca_workspace.py`
- `apps/backend/src/itx_backend/services/review_workspace.py`
- `apps/web-dashboard/src/ca-dashboard.ts`

Current state:

- Backend APIs for client lists, client detail, handoffs, sign-offs, and exports exist.
- The web dashboard surface is still minimal and not a full operations product.

Why it matters:

- The reviewer workflow is technically present.
- The CA workspace is not yet a market-ready multi-client review product.

### 6. Consent handling is materially better, but policy depth is still limited

Verified in:

- `apps/backend/src/itx_backend/services/consent.py`
- `apps/backend/src/itx_backend/api/filing.py`
- `apps/extension/src/sidepanel/App.tsx`
- `apps/extension/src/sidepanel/panes/ConsentOnboardingPane.tsx`
- `apps/backend/src/itx_backend/services/filing_runtime.py`

Current state:

- Purpose-specific onboarding consents now exist for upload, portal autofill, regime comparison, reviewer sharing, submission, and optional extended retention.
- Sensitive actions are blocked until the required consent purposes are active.
- Persisted consents are shown in the submission flow.
- Consent revocation and purge are exposed in the UI.
- Reviewer counter-consent exists.

Still missing:

- Consent versioning, richer scope granularity, and more explicit policy surfaces for reviewer-specific or artifact-specific sharing.
- More mature consent copy and compliance review for production deployment.

### 7. Operational hardening is still shallow

Verified in:

- `apps/backend/src/itx_backend/main.py`
- `apps/backend/src/itx_backend/api/analytics.py`
- `.github/workflows/ci.yml`

Current state:

- CI is stricter than older audits implied: build, lint, typecheck, tests, compileall, and Python test suites are all present in one workflow.
- Runtime startup now validates database connectivity, document storage writability, and configuration sanity.
- The `/health` endpoint now exposes detailed check output.
- Observability and runtime dependency checks are still shallow beyond those baseline checks.

Why it matters:

- Build discipline is better than the stale docs suggested.
- Production readiness is still not there because observability, alerting, external dependency coverage, and operational dashboards are shallow.

## Product And Market Verdict

### What the repo can plausibly support now

The current product looks most credible as a narrow wedge for:

- resident individuals,
- salary-first filings,
- AIS/TIS/Form 16 plus common proof ingestion,
- manual login and manual final e-verification,
- human-approved guided autofill on supported pages.

### What it is not ready for yet

It is not market-complete for the broader Indian filing market because it still lacks enough depth in:

- broad portal-page coverage,
- robust DOM-backed adapters,
- complex taxpayer handling,
- full deduction and exemption coverage,
- production-grade replay automation and durable analytics,
- production-grade CA operations UI,
- parser accuracy baselines and broader fixture coverage.

### Practical readiness verdict

- Internal alpha: yes.
- Design-partner pilot for a narrow taxpayer wedge: possibly.
- Broad consumer launch: no.
- Broad CA-market launch: no.

## Highest-Priority Pending Work

1. Expand the current fixture-backed filing-path adapters into broader captured production portal coverage.
2. Expand rules-core from the current broader baseline into real complex-taxpayer coverage.
3. Expand the new parser-regression bank from synthetic fixtures into broader production-like extraction scorecards.
4. Turn durable replay and durable analytics into a real portal-regression and operations pipeline.
5. Build a real CA dashboard on top of the existing APIs.
6. Deepen consent policy granularity and operator review UX.
7. Deepen validation-help translation and selector-drift recovery UX.
8. Strengthen observability, alerts, and environment health coverage.

## Short Answer

The hard part of the system is materially implemented and meaningfully more complete than the original audit baseline, but the product is still incomplete. The biggest remaining gap is last-mile reliability, coverage, and operator tooling required to safely support real portal variation and a broader taxpayer market.
