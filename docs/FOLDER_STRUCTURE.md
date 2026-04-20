# Folder Structure

A **pnpm + uv monorepo** with a TypeScript extension, a Python backend, background workers, shared schemas, and infra-as-code. Shared canonical types are generated from a single source (`packages/tax-schema`) so extension, backend, and workers stay in sync.

## Top-level layout

```
incometax-agent/
├── apps/
│   ├── extension/           # Chrome MV3 extension (TS + React)
│   ├── backend/             # FastAPI + LangGraph orchestrator (Python)
│   ├── workers/             # Doc-intelligence workers (Python)
│   └── web-dashboard/       # Optional CA/reviewer dashboard (Next.js)
├── packages/
│   ├── tax-schema/          # Canonical tax facts — JSON Schema → TS + Pydantic
│   ├── action-dsl/          # Browser action DSL — shared TS/Py types
│   ├── ui-kit/              # Shared React components for extension + dashboard
│   ├── portal-adapters/     # Per-portal-page adapters (pure TS, reused by tests)
│   └── rules-core/          # Deterministic tax rules (Python) with TS bindings
├── infra/
│   ├── terraform/           # Cloud infra (VPC, Postgres, object store, CDN)
│   ├── docker/              # Dockerfiles, compose, devcontainer
│   └── k8s/                 # Helm charts, manifests
├── docs/                    # Architecture, plan, use cases (this folder)
├── tests/
│   ├── e2e/                 # Playwright against portal snapshots
│   ├── fixtures/            # Sample AIS/TIS/Form 16/proof PDFs
│   └── personas/            # Canned taxpayer personas for replay
├── scripts/                 # Dev scripts, migrations, seed
├── .github/workflows/       # CI — lint/test/build/release
├── pnpm-workspace.yaml
├── pyproject.toml
├── turbo.json
└── README.md
```

## `apps/extension/` — Chrome MV3

```
apps/extension/
├── manifest.json            # MV3 — sidePanel, scripting, storage, host-only incometax.gov.in
├── src/
│   ├── sidepanel/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── panes/
│   │   │   ├── ChatPane.tsx
│   │   │   ├── DetectedDetailsPane.tsx
│   │   │   ├── PendingActionsPane.tsx
│   │   │   └── EvidencePane.tsx
│   │   ├── components/      # message bubbles, diff viewer, approval card
│   │   ├── hooks/
│   │   └── state/           # zustand/redux store
│   ├── background/
│   │   ├── service-worker.ts
│   │   ├── router.ts        # message routing between sidepanel ↔ content
│   │   ├── auth.ts          # token mgmt, refresh, device binding
│   │   ├── connector.ts     # WSS/SSE client to backend
│   │   └── action-runner.ts # executes backend-issued action DSL
│   ├── content/
│   │   ├── index.ts         # entry, bootstraps page adapter
│   │   ├── page-detector.ts # classifies current portal page
│   │   ├── field-map.ts     # label → selector resolution
│   │   ├── actions/
│   │   │   ├── fill.ts
│   │   │   ├── click.ts
│   │   │   ├── read.ts
│   │   │   └── validation.ts
│   │   └── adapters/        # per-page adapters (see packages/portal-adapters)
│   ├── injected/
│   │   └── bridge.ts        # page-context bridge for React/Angular events
│   ├── secure-storage/
│   │   ├── crypto.ts        # WebCrypto wrapping
│   │   └── session.ts
│   └── shared/              # imports from @itx/tax-schema, @itx/action-dsl
├── public/
│   ├── icons/
│   └── sidepanel.html
├── vite.config.ts           # WXT/CRXJS or Vite + custom MV3 plugin
└── package.json
```

## `apps/backend/` — FastAPI + LangGraph

```
apps/backend/
├── pyproject.toml
├── src/
│   └── itx_backend/
│       ├── main.py                # FastAPI app factory
│       ├── config.py              # env, secrets, feature flags
│       ├── api/
│       │   ├── auth.py            # OAuth / session, device binding
│       │   ├── threads.py         # start/pause/resume LangGraph threads
│       │   ├── documents.py       # signed uploads, status
│       │   ├── actions.py         # approve / reject / execute
│       │   ├── tax_facts.py       # read canonical facts for a thread
│       │   └── websocket.py       # bidirectional extension channel
│       ├── agent/
│       │   ├── graph.py           # LangGraph StateGraph definition
│       │   ├── state.py           # Pydantic graph state
│       │   ├── nodes/
│       │   │   ├── bootstrap.py
│       │   │   ├── portal_scan.py
│       │   │   ├── document_intake.py
│       │   │   ├── extract_facts.py
│       │   │   ├── reconcile.py
│       │   │   ├── infer_itr.py
│       │   │   ├── missing_inputs.py
│       │   │   ├── ask_user.py
│       │   │   ├── fill_plan.py
│       │   │   ├── approval_gate.py
│       │   │   ├── execute_actions.py
│       │   │   ├── validate_response.py
│       │   │   ├── recovery.py
│       │   │   ├── submission_summary.py
│       │   │   ├── everify_handoff.py
│       │   │   └── archive.py
│       │   ├── tools/             # tool wrappers — browser, docs, rules
│       │   ├── prompts/           # system, node-specific, guardrails
│       │   └── checkpointer.py    # Postgres checkpoint adapter
│       ├── services/
│       │   ├── ai_gateway.py      # model routing + PII-redacted logging
│       │   ├── doc_client.py      # talks to workers
│       │   ├── rules_client.py    # talks to rules-core
│       │   ├── audit.py           # evidence/audit writes
│       │   └── consent.py         # DPDP consent ledger
│       ├── db/
│       │   ├── models/            # SQLAlchemy models (see DATA_MODEL.md)
│       │   ├── migrations/        # Alembic
│       │   └── session.py
│       ├── security/
│       │   ├── crypto.py
│       │   ├── pii.py             # redaction/masking
│       │   └── rate_limit.py
│       └── telemetry/
│           ├── tracing.py         # OpenTelemetry
│           └── metrics.py
└── tests/
    ├── agent/
    ├── api/
    └── rules/
```

## `apps/workers/` — Document Intelligence

```
apps/workers/
├── pyproject.toml
├── src/
│   └── itx_workers/
│       ├── queue.py               # Redis/RQ/Celery consumer
│       ├── pipelines/
│       │   ├── classify.py        # doc type: AIS/TIS/Form16/proof/statement
│       │   ├── text_extract.py    # PDF text layer
│       │   ├── table_extract.py   # structured tables
│       │   ├── ocr_fallback.py    # only when text layer fails
│       │   ├── entities.py        # PAN, TAN, employer, amounts, sections
│       │   └── normalize.py       # → canonical tax-fact schema
│       ├── parsers/
│       │   ├── ais_json.py
│       │   ├── ais_csv.py
│       │   ├── ais_pdf.py
│       │   ├── tis.py
│       │   ├── form16.py
│       │   ├── form16a.py
│       │   ├── salary_slip.py
│       │   ├── interest_certificate.py
│       │   ├── rent_receipt.py
│       │   ├── home_loan_cert.py
│       │   ├── elss_ppf.py
│       │   └── broker_capgain.py
│       ├── reconcile/
│       │   ├── ais_vs_docs.py
│       │   ├── duplicates.py
│       │   └── severity.py
│       └── security/
│           ├── virus_scan.py
│           └── sanitize.py
└── tests/
    └── fixtures/                  # mirrored from /tests/fixtures
```

## `packages/tax-schema/` — Canonical tax facts

Single source of truth. JSON Schema compiled into both TypeScript (`.d.ts`) and Python (`pydantic` models) at build time.

```
packages/tax-schema/
├── schemas/
│   ├── taxpayer.json
│   ├── assessment_year.json
│   ├── income/
│   │   ├── salary.json
│   │   ├── house_property.json
│   │   ├── capital_gains.json
│   │   ├── other_sources.json
│   │   └── business_presumptive.json
│   ├── deductions/
│   │   ├── chapter_vi_a.json
│   │   └── standard.json
│   ├── tax_paid/
│   │   ├── tds.json
│   │   ├── tcs.json
│   │   └── advance_self_assessment.json
│   ├── bank_refund.json
│   ├── regime_choice.json
│   ├── residential_status.json
│   └── evidence.json
├── scripts/
│   ├── build-ts.ts
│   └── build-py.py
└── dist/
    ├── ts/
    └── py/
```

## `packages/action-dsl/`

```
packages/action-dsl/
├── spec.md                        # human-readable DSL spec
├── schema/
│   ├── fill.json
│   ├── click.json
│   ├── read.json
│   ├── navigate.json
│   └── validate.json
└── dist/
    ├── ts/
    └── py/
```

## `packages/portal-adapters/`

Per-page adapters. Each adapter exports:

- `detect(dom): boolean`
- `getFormSchema(dom): FormSchema`
- `fill(dom, plan): FillResult`
- `readValidation(dom): ValidationError[]`

```
packages/portal-adapters/
├── src/
│   ├── registry.ts
│   ├── base.ts
│   ├── pages/
│   │   ├── login.ts
│   │   ├── dashboard.ts
│   │   ├── file-return-start.ts
│   │   ├── itr-selection.ts
│   │   ├── personal-info.ts
│   │   ├── salary-schedule.ts
│   │   ├── house-property.ts
│   │   ├── other-sources.ts
│   │   ├── capital-gains.ts
│   │   ├── deductions-vi-a.ts
│   │   ├── tax-paid.ts
│   │   ├── bank-account.ts
│   │   ├── regime-choice.ts
│   │   ├── summary-review.ts
│   │   └── everify.ts
│   └── utils/
│       ├── fuzzy-label.ts
│       └── selector-fallback.ts
└── tests/
    └── snapshots/                 # captured DOM snapshots per page
```

## `packages/rules-core/` — Deterministic tax rules

```
packages/rules-core/
├── pyproject.toml
├── src/
│   └── rules_core/
│       ├── engine.py
│       ├── versions.py            # rule-version registry (AY-specific)
│       ├── eligibility/
│       │   ├── itr1.py
│       │   ├── itr2.py
│       │   └── itr4.py
│       ├── caps/
│       │   ├── chapter_vi_a.py
│       │   └── standard_deduction.py
│       ├── regime/
│       │   └── old_vs_new.py
│       ├── reconcile/
│       │   ├── mismatch_severity.py
│       │   └── duplicate.py
│       └── schedules/
│           ├── required_schedules.py
│           └── disclosure_checks.py
└── tests/
    └── cases/                     # golden YAMLs per rule
```

## `infra/`

```
infra/
├── terraform/
│   ├── envs/
│   │   ├── dev/
│   │   ├── staging/
│   │   └── prod/
│   └── modules/
│       ├── network/
│       ├── postgres/
│       ├── object-store/
│       ├── secrets/
│       └── observability/
├── docker/
│   ├── backend.Dockerfile
│   ├── workers.Dockerfile
│   ├── docker-compose.yml
│   └── devcontainer/
└── k8s/
    ├── charts/
    └── overlays/
```

## `tests/`

```
tests/
├── e2e/
│   ├── portal-snapshots/          # captured DOM for replay
│   ├── personas/                  # persona-driven filing journeys
│   └── playwright.config.ts
├── fixtures/
│   ├── ais/                       # real-shape, synthetic-content AIS PDFs/JSON
│   ├── tis/
│   ├── form16/
│   ├── proofs/
│   └── broker/
└── personas/
    ├── salaried_simple.yaml
    ├── salaried_multi_employer.yaml
    ├── capital_gains_lite.yaml
    └── mismatch_heavy.yaml
```

## Shared conventions

- **Type parity** — every canonical type lives once in `packages/tax-schema` and is generated into TS + Py.
- **Action DSL parity** — extension and backend import the same schema from `packages/action-dsl`.
- **Rule version pinning** — every audit-log row records the `rules-core` version that produced it.
- **No cross-app imports** — apps consume shared logic only via `packages/*`.
- **Fixtures are synthetic** — never commit real taxpayer data, even anonymized.
