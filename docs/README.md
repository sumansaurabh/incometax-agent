# Income Tax Agent — Documentation Index

An AI copilot for the **Indian Income Tax e-Filing portal** (`incometax.gov.in`) delivered as a **Chrome Manifest V3 extension** with a persistent side-panel chat, backed by a **LangGraph** orchestrator, a document intelligence pipeline, a deterministic tax-rules engine, and a Postgres-backed evidence/audit store.

## Product framing

> **The fastest compliant way to file on the official portal with AI assistance.**

The agent does **not** replace the official filing system. It reads the current portal page, ingests AIS / TIS / Form 16 / proofs, normalizes them into a canonical tax schema, proposes a fill plan, and executes DOM actions **only after user approval**. It pauses at every risky step (submission, e-verification, regime switch, bank/refund account, OTP / DSC handoff).

## Scope (MVP v1)

- Resident individuals
- Salary + interest + common 80C / 80D proofs
- ITR-1 first, ITR-2 next for capital-gains lite
- Manual login and manual e-verification (user-controlled)
- Uploads: AIS / TIS / Form 16 / investment proofs

## Document map

| File | Purpose |
|---|---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 6-layer system architecture, services, LangGraph node design, DOM automation hierarchy |
| [FOLDER_STRUCTURE.md](./FOLDER_STRUCTURE.md) | Monorepo layout — extension, backend, workers, shared packages, infra |
| [DATA_MODEL.md](./DATA_MODEL.md) | Postgres schema — identity, documents, tax facts, agent state, portal mapping, audit |
| [PLAN.md](./PLAN.md) | Phase-by-phase engineering roadmap (Phase 0 → Phase 5) with deliverables and exit criteria |
| [USE_CASES.md](./USE_CASES.md) | 50+ concrete user-facing use cases the system can fulfill |
| [SECURITY.md](./SECURITY.md) | DPDP posture, PII handling, key management, anti-phishing, audit trail |

## Non-negotiables

1. **DOM-first automation.** No vision-only clicking. No arbitrary JS execution from model output.
2. **Deterministic tax math.** The LLM never computes totals, caps, or regime outcomes.
3. **Evidence for every field.** Each filled value links to a source doc + page + snippet + rule version.
4. **Human approval gates.** Fill batches, submission, regime switch, bank change, e-verification.
5. **Data minimization.** DPDP-aligned consent ledger, short retention, encrypted at rest, masked logs.
6. **Official domain only.** Extension host permission restricted to the verified e-Filing portal.
