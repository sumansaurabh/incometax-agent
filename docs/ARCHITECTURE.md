# Architecture

## 1. Six-layer view

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. Extension UI Layer (React side panel)                         │
│    chat · detected details · action approvals · evidence viewer  │
├──────────────────────────────────────────────────────────────────┤
│ 2. Browser Control Layer (MV3 content scripts + service worker)  │
│    page adapters · field map · fill/click/read · error scraping  │
├──────────────────────────────────────────────────────────────────┤
│ 3. Agent Layer (LangGraph orchestrator, Python/FastAPI)          │
│    planner · portal interpreter · reasoner · filler · verifier   │
├──────────────────────────────────────────────────────────────────┤
│ 4. Data Layer (Postgres + object storage + Redis queue)          │
│    users · docs · tax facts · threads · checkpoints · audit      │
├──────────────────────────────────────────────────────────────────┤
│ 5. Document Intelligence Layer (workers)                         │
│    classify · text · tables · OCR fallback · normalize           │
├──────────────────────────────────────────────────────────────────┤
│ 6. Compliance + Security Layer                                   │
│    consent ledger · encryption · PII mask · approvals · rate lim │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Runtime topology

```
   ┌──────────────────┐       WSS/HTTPS       ┌───────────────────────┐
   │  Chrome MV3 Ext  │ ───────────────────▶  │  API / AI Gateway     │
   │ sidepanel · CS   │ ◀───────────────────  │ (FastAPI, auth, PII)  │
   └────────┬─────────┘    action intents      └──────────┬────────────┘
            │                                             │
            │ message passing                             │ graph run
            │                                             ▼
   ┌────────▼─────────┐                       ┌───────────────────────┐
   │ Content scripts  │                       │ LangGraph Orchestrator│
   │ on e-Filing tab  │                       │ (checkpoints in PG)   │
   └──────────────────┘                       └──┬────────────┬───────┘
                                                 │            │
                                    ┌────────────▼──┐   ┌─────▼──────────┐
                                    │ Tax Rules Svc │   │ Doc Intel Svc  │
                                    │ (deterministic│   │ (workers, OCR) │
                                    └───────┬───────┘   └─────┬──────────┘
                                            │                 │
                                            ▼                 ▼
                                   ┌───────────────────────────────────┐
                                   │ Postgres · Object Store · Redis   │
                                   └───────────────────────────────────┘
```

## 3. Core services

| Service | Responsibility |
|---|---|
| **API / AI Gateway** | Auth, session binding, model routing, system-prompt injection, PII redaction before logging, per-user rate limits |
| **Agent Orchestrator** | Runs LangGraph threads, manages pause/resume, emits next action (ask / parse / fill / wait-OTP) |
| **Tax Rules Service** | ITR form eligibility, income-head classification, deduction caps, old-vs-new regime compare, mismatch severity, schedule detection |
| **Document Processing Service** | Upload pipeline, classify → parse → OCR fallback → normalize → reconcile |
| **Browser Action Service** | Emits structured action DSL to the extension and validates responses |
| **Audit / Evidence Service** | Records every claim with value + source file + page + snippet + confidence + rule version + approval state |

## 4. Why LangGraph

Tax filing is a **state machine with branches, retries, human approval, and resumability** — not a chat loop. LangGraph gives us checkpointed thread state in Postgres so that portal timeouts, model failures, and user walk-aways are all recoverable.

### Graph state (per filing thread)

- `user_profile`, `assessment_year`, `filing_mode`
- `portal_page`, `detected_fields`, `current_step`
- `uploaded_docs[]`, `extracted_facts[]`
- `unresolved_questions[]`, `recommended_actions[]`
- `approval_state`, `browser_execution_state`, `submission_state`

### Nodes

```
session_bootstrap
  → portal_context_scan
    → document_intake
      → extract_tax_facts
        → reconcile_ais_tis
          → infer_itr_type
            → detect_missing_inputs
              ↘ ask_user_question ─┐
                                   ↓
              ↗ prepare_fill_plan ─┘
            → await_user_approval
              → execute_browser_actions
                → validate_portal_response
                  ↘ recovery_node (selector / validation drift)
                  ↘ prepare_submission_summary
                    → await_submission_approval
                      → await_everify_handoff
                        → archive_filing_artifacts
```

## 5. Chrome extension architecture (MV3)

```
extension/
  sidepanel/          React chat UI (primary surface, persistent)
  background/         service worker — routing, websocket, auth
  content/            per-portal-page adapters on e-Filing DOM
  injected/           small in-page bridge for framework events
  secure-storage/     encrypted ephemeral session metadata
  connector/          WSS/SSE client to backend
```

**Permissions (tight):**

- host permission: `https://*.incometax.gov.in/*` only
- `sidePanel`, `scripting`, `storage`, `activeTab`

**Messaging pattern:**

- `content → background`: page context, field map, validation errors
- `sidepanel → background`: user input, approvals, uploads
- `background → content`: execute fill/click/read via structured action DSL

## 6. Automation hierarchy (DOM-first)

```
1. DOM mapping              — detect page, labels, fields, validation state
2. Semantic page adapter    — “salary schedule”, “bank account”, “deductions”
3. Structured fill plan     — {fields: [...], approvals_required: true}
4. User approval            — batch preview in side panel
5. Execution                — content script fills & clicks
6. Read-after-write         — re-read page, scrape validation errors
7. Escalation               — user confirms or switches to guided mode
```

### Browser action DSL (closed set only)

```ts
get_current_page()
get_form_schema()
read_field(label | selector)
set_field(label | selector, value)
click(label | selector)
get_validation_errors()
get_summary_values()
capture_dom_snapshot()
```

**Disallowed:** arbitrary JS from model output, synthetic click loops, headless submit without approval.

## 7. LLM boundary

| LLM does | Deterministic code does |
|---|---|
| Classify docs & fields | Totals, section caps |
| Propose questions for missing inputs | Duplicate detection |
| Explain portal errors | Regime comparison math |
| Disambiguate labels | Mismatch categorization |
| Summarize progress | Mapping canonical facts → portal fields |

## 8. Tool-call contract

Every model-initiated tool call must include:

```json
{
  "tool": "browser.fill_fields",
  "reason": "Populate salary section after user approval",
  "requires_approval": true,
  "sensitivity": "medium",
  "fallback": "ask_user",
  "fields": [
    {"label": "Gross Salary", "value": 1845000, "source_doc": "form16_2024", "source_page": 1, "confidence": 0.97}
  ]
}
```

## 9. Recovery modes

- **Selector break** → re-scan labels → fuzzy-match → user-click-to-teach → persist mapping
- **Portal validation error** → parse error → structured reason → targeted question → retry
- **Session timeout** → persist checkpoint → prompt re-login → resume thread
- **Unsupported case** → downgrade to guided checklist → export handoff summary

## 10. Observability

Traced per thread: node entered, model chosen, tool calls, retries, selector hits/misses, approval latency, validation errors, extraction confidence distribution, rule-engine version, page adapter version. All logs PII-masked by default.
