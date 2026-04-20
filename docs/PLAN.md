# Engineering Plan

A phased, exit-criteria-driven roadmap. Each phase ships something a real user can touch and ends with a go/no-go gate. Phases are sequential but internal workstreams inside a phase run in parallel.

## Phase 0 — Foundations (2–3 weeks)

**Goal:** Stand up the monorepo, shared schemas, and a walking skeleton of extension ↔ backend.

### Workstreams

- **Monorepo setup** — pnpm workspaces + uv + Turbo + CI.
- **Canonical tax schema** — first cut of `packages/tax-schema` covering salary, deductions (80C/80D), bank, regime, residential status; build outputs for TS + Py.
- **Action DSL** — `packages/action-dsl` with `fill`, `click`, `read`, `get_form_schema`, `get_validation_errors`.
- **Backend skeleton** — FastAPI app, auth stub, Postgres + Alembic migrations, LangGraph state graph with `bootstrap → portal_scan → ask_user → archive` only.
- **Extension skeleton** — MV3 manifest with side panel, host permission pinned to `incometax.gov.in`, WSS connection to backend, echo chat.
- **Observability baseline** — OpenTelemetry wiring, structured logs with PII redaction by default.

### Exit criteria

- User installs extension, logs in, opens side panel on the portal, sees a chat that round-trips to backend.
- Backend runs a single LangGraph thread to completion with checkpoint persisted in Postgres.
- CI green: lint, type-check, unit tests on both sides, schema-generation check.

## Phase 1 — Portal Copilot (read-only) (3–4 weeks)

**Goal:** Detect portal page, explain what the user is looking at, answer "what is this step?" — **no filling yet**.

### Workstreams

- **Page detector** — `packages/portal-adapters` covers: dashboard, file-return-start, ITR selection, personal info, salary schedule, deductions-VI-A, tax-paid, summary-review.
- **DOM reader** — `get_form_schema`, `read_field`, `get_validation_errors` implemented.
- **Agent explanation mode** — prompts & nodes: `explain_current_step`, `list_required_info`.
- **Evidence viewer v0** — side-panel pane shows what the agent detected from the current page.
- **Selector-drift telemetry** — every page-adapter mismatch logged for tuning.

### Exit criteria

- On 10 real portal pages, the agent correctly identifies the page and describes required inputs in ≥ 95% of snapshots.
- No write actions have been emitted.

## Phase 2 — Document Intelligence (4–5 weeks)

**Goal:** Upload + parse + normalize AIS/TIS/Form 16 + common proofs into canonical facts with evidence.

### Workstreams

- **Upload pipeline** — signed URL upload, virus scan, sanitizer, queue.
- **Parsers** — AIS (JSON/CSV/PDF), TIS, Form 16, Form 16A, interest certificates, rent receipts, ELSS/PPF proofs, home-loan certificates, broker capital-gain statements.
- **Entity extraction** — PAN, TAN, employer, amounts, sections, dates.
- **Normalization** — parsers output only into `packages/tax-schema`; no freeform shapes.
- **Reconciliation** — AIS vs docs vs user-stated; categorize mismatches (harmless / duplicate / missing-doc / under-reporting / prefill-issue / human-decision).
- **Missing-input engine** — turn unresolved facts into a prioritized question list.
- **Evidence viewer v1** — per-fact drill-down: source document, page, snippet, confidence, extractor version.

### Exit criteria

- On a fixture bank of 50 synthetic taxpayer cases, canonical-fact extraction precision ≥ 0.95 for Form 16 fields and ≥ 0.90 for AIS line items.
- Every fact in the DB has a non-null evidence pointer and rule version.

## Phase 3 — Guided Autofill (4–6 weeks)

**Goal:** Agent proposes fill plans → user approves → content script fills → validation read-back. **No submission yet.**

### Workstreams

- **Fill-plan generator** — diff between canonical facts and current portal state; batched by page.
- **Approval UI** — side-panel card showing every field, value, source, and confidence; one-tap approve / reject / edit.
- **Content-script filler** — action DSL execution with read-after-write and per-field result reporting.
- **Recovery node** — selector break → relabel → user-click-to-teach → persist mapping.
- **Tax-rules engine v1** — ITR-type inference, deduction caps, old-vs-new regime comparison, required-schedule detection.
- **Audit trail v1** — `field_fill_history`, `filing_audit_trail` populated for every fill.

### Exit criteria

- End-to-end on 5 persona fixtures: agent fills salary + deductions + tax-paid + bank pages with ≤ 1 manual correction per filing.
- 0 instances of a fill executed without matching `approvals` row.

## Phase 4 — Completion Flow (3–4 weeks)

**Goal:** Draft → summary → approval gate → hand-off to portal submission and e-verification.

### Workstreams

- **Submission summary** — totals, taxable income, tax payable, refund due, mismatches, disclosure checks.
- **Approval gate (submit)** — hard stop, explicit consent text, hashed into `consents`.
- **E-verification handoff** — UI branches for Aadhaar OTP / EVC / net banking / DSC; agent does **not** automate OTP entry; user drives the final step.
- **Filing artifact archive** — ITR-V, JSON export, evidence bundle stored and downloadable.
- **Revised-return support** — thread can branch to a revision with prior-return context.

### Exit criteria

- Closed-loop filing on 3 live demo accounts (team members) with all approval rows captured and filed artifacts archived.
- No automation after the "Submit" click — manual verification only.

## Phase 5 — Scale & Hardening (ongoing)

**Goal:** Widen taxpayer coverage, harden against drift, add CA workspace, deepen analytics.

### Workstreams

- **Coverage** — capital gains (full), multi-employer, house property, ITR-4 presumptive, foreign income detection (escalate-only).
- **CA workspace** — reviewer dashboard, multi-client approvals, audit exports.
- **Portal-drift autopilot** — nightly snapshot diffing + adapter regeneration PRs.
- **Replay harness** — every failed thread can be replayed against the captured DOM snapshot.
- **Analytics** — extraction accuracy per doc type, questions per filing, approval latency, selector failure rate, abandonment stage, time-to-file.
- **Advanced security** — WAF, anomaly detection on tool-call patterns, rotating per-file encryption keys.
- **Offline utility export** — produce portal-compatible JSON for the offline utility as a fallback path.

## Cross-cutting tracks (run every phase)

- **Security** — quarterly threat-model review, pen-test before public beta.
- **Fixtures** — synthetic AIS/TIS/Form 16 generators grown each phase; fixtures never contain real PII.
- **Documentation** — user-facing help, CA-facing guide, developer-facing adapter-writing guide.
- **Rule-version discipline** — every rule change tagged; old filings remain reproducible with their original version.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Portal UI changes mid-season | Page adapters + drift telemetry + replay harness; fallback to guided mode |
| Wrong document extraction | Confidence thresholds + human-verify flag + always-on evidence link |
| LLM overconfidence on tax logic | Rules engine owns all math; LLM constrained to classification/explanation |
| User trust on PAN/salary/bank data | DPDP-aligned consent, encryption, short retention, per-action approval |
| OTP / verification friction | Never automate OTP; always hand off |
| Scope creep into legal advice | Explicit "we are not CAs" disclosure; escalation path |
| Mismatches between AIS and docs | Severity categorization + targeted questions, never silent overrides |

## Team shape (indicative)

- 1 EM / tech lead
- 2 backend (FastAPI + LangGraph)
- 1 doc-intel engineer (parsers + OCR)
- 1 tax-rules engineer (or senior backend with CA consultation)
- 2 extension / frontend
- 0.5 DevOps / infra
- CA consultant on retainer for rule validation
- Designer for side-panel UX

## Definition of done (per feature)

1. Canonical types in `packages/tax-schema`.
2. Deterministic logic in `packages/rules-core` with golden-YAML tests.
3. Page adapter + snapshot tests in `packages/portal-adapters`.
4. LangGraph node with prompt + tool-call contract.
5. Evidence writes to audit trail with rule/adapter versions.
6. Approval gate for any field that changes portal state.
7. User-visible copy reviewed by CA consultant.
8. Fixture-based e2e test added to replay harness.
