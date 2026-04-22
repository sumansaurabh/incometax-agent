# Agentic Upgrade Plan — IncomeTax Agent

**Status:** Plan only. No code changes yet.
**Owner:** sumansaurabh
**Date:** 2026-04-23

---

## 1. The bug, in one paragraph

The "IncomeTax Agent" is not an agent. The chat endpoint `POST /api/chat/message` routes to `ChatService.handle_message` in `apps/backend/src/itx_backend/services/chat.py`. That method calls `_build_agent_response` (lines 58–151), which is a chain of `if "keyword" in message.lower()` branches:

| Branch | Trigger keywords |
|---|---|
| Filing readiness card | `"file"` AND (`"return"` OR `"itr"` OR `"tax"`) |
| Upload help | `"upload"` OR `"document"` |
| Refund | `"refund"` |
| Regime | `"regime"` |
| Semantic search | any other message, only if documents exist |
| **Hardcoded fallback** (lines 148–151) | everything else |

The fallback is the exact string the screenshots show:

> *"Tell me what you want to file or upload your tax documents. For example: **File my income tax return for the current year**."*

So when the user typed **"what should I select in the dropdown"** or **"what is AIS or TIS?"**, no branch matched (no "file"+"return", no "upload", no "refund", no "regime"), and because the semantic search path only returns a response when a chunk matches with a non-trivial score, unrelated queries like "what is AIS" fell through to the fallback. Even when the semantic search *does* fire, the response is just `"I found a document-backed match in **<filename>**"` — it never actually **answers** anything, because there is no LLM in the loop.

### Corroborating evidence in the repo

- `apps/backend/src/itx_backend/agent/tools/` — **empty directory.** No tools defined.
- `apps/backend/src/itx_backend/agent/prompts/` — **empty directory.** No prompts defined.
- `apps/backend/src/itx_backend/agent/nodes/*.py` — every node is a 3-line stub that mutates `state.current_node` and appends a canned string. No reasoning, no LLM call.
- `apps/backend/src/itx_backend/agent/graph.py` — a `AgentGraph` class that iterates over the 20 node stubs sequentially. It is **never called from the chat endpoint**.
- `apps/backend/src/itx_backend/services/ai_gateway.py` — **5 lines**, only re-exports a PII redactor. No LLM client.
- `config.py` has `openai_api_key`, but it's used only for **embeddings** in `embedding_service.py`. There is no chat-completion client anywhere.
- `grep -r "anthropic\|chat.completions\|messages.create" apps/backend` returns **zero matches**.

### What "agentic" would actually mean

An agent here needs:

1. An **LLM** that reads the user message + conversation history + portal context and decides what to do.
2. A **tool registry** the LLM can call: document search, portal field reader, tax-rule lookup, web search for law/notifications, calculators, etc.
3. A **tool-calling loop** that executes the chosen tool, feeds the result back, and lets the LLM respond in natural language (or call another tool).
4. **Context injection**: the current portal URL, the visible form fields, the thread's uploaded/indexed documents, the active assessment year.

None of that exists today.

---

## 2. 40 use cases the agent must handle

These are grouped by which tool(s) the LLM would invoke. Every one of these is a real question a user on the e-Filing portal could reasonably ask the side-panel agent. Today, **every single one of them hits the hardcoded fallback** (or at best the weak semantic-search path).

### A. Portal-context questions — need a `get_portal_context` tool
*(reads the currently visible page/form the extension has scraped)*

1. **"What should I select in the dropdown?"** — agent reads the focused field (e.g. "Select Filing Type"), and explains options (Original / Revised / Belated / U) based on the user's situation.
2. **"What does 'Select Assessment year' mean? Which one applies to me?"** — explains AY vs FY, recommends AY 2025-26 for FY 2024-25 income.
3. **"Am I audited u/s 44AB?"** — explains the 44AB threshold (₹1Cr/₹10Cr turnover, ₹50L professional receipts) and asks targeted qualifying questions.
4. **"Which ITR form do I need?"** — reads the portal state and walks through ITR-1 / 2 / 3 / 4 eligibility based on the user's income sources.
5. **"What does 'Are you filing u/s 139(1)'..' mean?"** — explains 139(1), 139(4), 139(5), 139(8A) sections based on the dropdown option.
6. **"Why is the Continue button disabled?"** — reads which mandatory fields are unfilled and points them out.
7. **"I clicked Continue but got an error — what now?"** — reads the portal error banner and translates it.
8. **"Where do I find my filing status?"** — navigates the user to `/iec/foservices/#/dashboard/filingStatus`.

### B. Tax-concept questions — need a `kb_lookup` tool
*(queries an internal curated tax glossary / rule pack)*

9. **"What is AIS or TIS?"** — returns the Annual Information Statement vs Taxpayer Information Summary definitions and when each is used.
10. **"What's the difference between Old and New regime?"** — slab-by-slab comparison for AY 2025-26, who benefits from each.
11. **"What is 80C? What qualifies?"** — lists allowable instruments, ₹1.5L cap.
12. **"What is HRA exemption? How is it calculated?"** — explains the three-limb formula and asks for the needed inputs.
13. **"What is standard deduction? Do I get it?"** — explains ₹50k / ₹75k (new regime), salaried-only eligibility.
14. **"What is TDS vs advance tax vs self-assessment tax?"** — definition + where each appears in Form 26AS / AIS.
15. **"What is Section 87A rebate?"** — explains ₹25k (new) / ₹12.5k (old) limits.
16. **"What is LTCG vs STCG?"** — covers equity 10%/15%, debt slab, property indexation.

### C. Document-backed questions — need `document_search` + LLM synthesis
*(agent already has the embedding + qdrant pipeline; the missing piece is an LLM that reads the retrieved chunks and synthesizes an answer)*

17. **"What's my gross salary according to my Form 16?"** — RAG over Form 16, returns the exact figure with a citation.
18. **"How much TDS was deducted by my employer?"** — pulls from Form 16 Part A.
19. **"Summarise my AIS."** — lists all reported income heads with amounts.
20. **"Is there a mismatch between my Form 16 and AIS?"** — cross-compares indexed facts from both.
21. **"What deductions have I already claimed according to the documents I uploaded?"** — scans all 80C/80D-style entries.
22. **"How much interest did I earn from savings accounts?"** — pulls from bank interest certificates / AIS SFT entries.
23. **"What is my PAN / Aadhaar on the uploaded docs?"** — sanity-check the header of Form 16.
24. **"Do I have capital gains from mutual funds?"** — searches CAS / broker statements.

### D. Compute / calculator questions — need a `tax_calc` tool
*(pure-Python calculators, already scaffolded in `packages/rules-core` and `tax-schema`)*

25. **"What's my tax liability under the old regime?"** — runs the calculator with extracted facts.
26. **"What's my tax liability under the new regime?"** — same, new slabs.
27. **"Which regime saves me more?"** — runs both and returns the delta.
28. **"If I invest another ₹50k in ELSS, how much tax do I save?"** — what-if on 80C.
29. **"How much refund will I get?"** — tax liability minus TDS/advance tax.
30. **"Do I owe any self-assessment tax?"** — positive version of the above.
31. **"What's my effective tax rate?"** — computed ratio.
32. **"If I switch to old regime, will I still get 87A?"** — rebate eligibility check.

### E. Live-law / notification questions — need a `web_search` tool
*(restricted to incometax.gov.in, cbic.gov.in, incometaxindia.gov.in, a whitelisted set of reputable tax publications)*

33. **"What's the ITR filing deadline this year?"** — checks current CBDT notifications.
34. **"Has the deadline been extended?"** — web search, because this changes year-to-year.
35. **"What's the penalty u/s 234F if I file late?"** — fetches the current amount.
36. **"Is there a new tax regime update for this AY?"** — surfaces CBDT circulars.
37. **"What's the latest on Section 87A rebate for STCG?"** — there's been active litigation; needs a live lookup.

### F. Procedural / flow questions — need `portal_nav` + `how_to` tool

38. **"How do I e-verify my return after filing?"** — explains Aadhaar OTP / net-banking / DSC options and drops a link.
39. **"How do I download my filed ITR-V?"** — navigates to View Filed Returns.
40. **"What happens if I don't e-verify within 30 days?"** — explains the deemed-not-filed consequence and revival route.

---

## 3. Why the current architecture can't handle any of these

Every one of the 40 use cases above requires at least **one of**:

- calling an LLM to interpret the user's natural-language question,
- calling a tool (portal context, document RAG with synthesis, calculator, web search, KB lookup),
- feeding the tool result back to the LLM for a final answer.

The current `_build_agent_response` has none of those. It is a keyword switchboard with a fallback string.

---

## 4. Implementation plan

This is split into **Phase 0** (land the agent loop) and **Phase 1–3** (progressively add tools). Phase 0 alone will fix the reported bug; every subsequent phase widens coverage of the 40 use cases.

### Phase 0 — Wire in a real LLM and tool-calling loop

**Files to add**

- `apps/backend/src/itx_backend/agent/llm_client.py` — thin wrapper around the Anthropic SDK (`claude-sonnet-4-6` as default; model configurable via env). Handles prompt caching of system prompt + tool schemas.
- `apps/backend/src/itx_backend/agent/tool_registry.py` — decorator-based registry, each tool has `name`, `description`, JSON-schema input, and an async `run(thread_id, args) -> dict`.
- `apps/backend/src/itx_backend/agent/runner.py` — the tool-calling loop: call LLM with system prompt + messages + tool schemas, execute any requested tools, feed results back, repeat until the LLM responds without a tool call or a step cap is hit.
- `apps/backend/src/itx_backend/agent/prompts/system.md` — the system prompt (role: Indian income-tax filing assistant; constraints; citation style; safety).

**Files to change**

- `apps/backend/src/itx_backend/services/chat.py` — replace `_build_agent_response` with a call into `runner.run(thread_id, message, context)`. Keep the DB persistence unchanged. Keep a minimal safety-net fallback for when the LLM client fails, but it must be a transient-error message, not a canned sales pitch.
- `apps/backend/src/itx_backend/config.py` — add `anthropic_api_key`, `agent_model`, `agent_max_steps`.
- `apps/backend/pyproject.toml` — add `anthropic` dep.

**Acceptance: after Phase 0, the 16 use cases in groups A and B above must return non-fallback, grounded answers** (A needs the portal context tool from Phase 1, but B works with just an LLM + the system prompt).

### Phase 1 — Context + KB tools

Add these tools to the registry:

- **`get_portal_context(thread_id)`** — returns the last scraped portal state the Chrome extension posted (current URL, page title, visible form fields, focused field, any error banners). Requires a small schema in the `portal_snapshots` table (already hinted at in `packages/portal-adapters`). This unblocks group A (use cases 1–8).
- **`kb_lookup(topic, query)`** — queries a curated static JSON/YAML rule pack under `packages/rules-core`. Topics: `regimes`, `sections`, `forms`, `slabs`, `definitions`. Unblocks group B (9–16).

### Phase 2 — Document RAG with synthesis + calculators

- **`document_search(thread_id, query, top_k)`** — already exists as `document_service.semantic_search`. Wrap it as a tool. Unblock group C (17–24) by letting the LLM **read the returned chunks** and synthesize — that's the missing step today.
- **`tax_calc(regime, facts)`** — thin wrapper over `packages/rules-core`. Inputs: regime, salary, deductions, other income, tds. Output: tax, surcharge, cess, 87A, refund/payable. Unblocks group D (25–32).
- **`extract_facts(thread_id, heads)`** — pull a normalized fact sheet (gross salary, 80C total, TDS, etc.) from indexed documents so `tax_calc` can be called with real numbers.

### Phase 3 — Live lookups + procedural help

- **`web_search(query)`** — whitelisted to `incometax.gov.in`, `incometaxindia.gov.in`, `cbic.gov.in`, a short list of reputable publications (e.g. cleartax.in, taxmann.com) with clear citation. Unblocks group E (33–37).
- **`portal_nav(target)`** — returns a deep link + steps for portal destinations (e-verify, view filed returns, refund status, Form 26AS). Unblocks group F (38–40).
- **`how_to(flow_id)`** — static playbooks for procedural flows, versioned in `packages/rules-core/flows/`.

### Phase 4 — Evaluation harness

- A fixtures file `tests/agent/use_cases.yaml` with all 40 questions + expected-tool assertions + ideal-answer keywords.
- A replay harness (extend the existing `services/replay_harness.py`) that runs the 40 cases against a test thread with mock documents and asserts:
  - the **correct tool(s) were called** (not the fallback),
  - the answer **doesn't equal** the old fallback string,
  - for deterministic cases (calculators), numeric output is within tolerance.
- A CI gate that blocks any PR where the fallback rate across the 40 cases regresses.

---

## 5. Guardrails (non-negotiable)

- **No hardcoded response strings** may be added to `chat.py` or any new agent file. All text comes from the LLM.
- **Every tool result is cited** in the agent's reply (filename + page for documents, section number for KB, URL for web).
- **No hallucinated tax advice**: the system prompt must force the LLM to say "I don't know / please consult a CA" when a tool returns empty, rather than invent.
- **PII**: continue routing every LLM call through `security/pii.py:redact_payload` before logging.
- **Model routing**: Opus for the one-shot reasoning steps, Sonnet for the tool-loop steps (configurable per env).
- **Cost/step cap**: `agent_max_steps = 6` default; hard stop on infinite tool loops.

---

## 6. Out of scope for this plan

- Voice, multi-language — separate track.
- E-filing submission automation — covered by `packages/action-dsl` and `agent/nodes/execute_actions.py`, orthogonal to the Q&A bug this plan fixes.
- Re-architecting the empty LangGraph scaffolding. Phase 0 adopts a simpler tool-calling loop. The LangGraph nodes can be revisited once the chat loop works end-to-end.

---

## 7. Portal form-filling actions — 20 use cases

Q&A (sections 2–4) is only half the product. The real win is the agent **filling the portal form** end-to-end for the user, using the documents they uploaded, the tax calculator, and the already-extracted facts. The primitives for this already exist in `packages/action-dsl/` (`fill`, `click`, `read`, `get_form_schema`, `get_validation_errors`) and the extension side-panel can already execute them. What's missing is the agent that **decides what to fill**, field by field, and **handles the branching logic** of the portal flow.

### Classes of form-fill action

- **Deterministic fills** — a document fact maps 1:1 to a portal field (PAN, name, gross salary).
- **Derived fills** — value comes from a calculator or reconciliation across documents (regime choice, ITR form type, net taxable income).
- **Choice fills** — the agent chooses between options based on user profile (filing type: Original vs Revised; 44AB: Yes/No).
- **Guarded fills** — the agent *proposes* a value but requires explicit user confirmation before writing (anything that changes tax liability by >₹5k, any regime switch, any Yes/No on audit/political-party questions).
- **Navigation actions** — click Continue, Save Draft, Next Section, Proceed to Validation.

Every writing action is surfaced to the user as a diff preview before the extension executes the `fill`/`click` DSL op — no silent writes.

### The 20 form-fill use cases

These are ordered roughly by how deep into the ITR flow they sit. Each one maps to one LLM plan step + N `fill`/`click` DSL ops. Each case also has an **inputs** (what the agent needs to read/have) and a **gate** (Yes = needs user confirmation before write; No = safe deterministic write).

#### Page: File Income Tax Return (the page in the screenshot)

1. **Select Assessment Year** — picks the right AY from today's date (AY 2025-26 for FY 2024-25). Inputs: system clock. Gate: No.
2. **Select Filing Type** — picks Original / Revised / Belated / 139(8A) based on whether an acknowledgment number already exists for this PAN + AY in the uploaded docs or prior threads. Inputs: document search + thread history. Gate: Yes (one-time).
3. **Audit u/s 44AB / political party u/s 13A** — defaults to No for salaried profiles; flips to Yes only if documents show business turnover > ₹1Cr / professional receipts > ₹50L, or user self-declared. Inputs: AIS / Form 16 / user profile. Gate: Yes.
4. **Select ITR Type** — infers ITR-1 / 2 / 3 / 4 from income heads detected (salary only → ITR-1; + capital gains → ITR-2; + business → ITR-3/4). Inputs: extracted facts. Gate: Yes.
5. **Proceed to next page** — clicks Continue once all four above are filled and valid. Inputs: `get_validation_errors`. Gate: No.

#### Page: Personal Information

6. **PAN, name, DOB, Aadhaar, mobile, email** — lifted from Form 16 Part A and the user's profile record. Inputs: document RAG + user row. Gate: No (low-risk; already on file).
7. **Address** — from Form 16 or user profile; prefers the most recent source. Gate: No.
8. **Nature of Employment** — Govt / PSU / Pensioner / Private based on Form 16 employer TAN category. Inputs: Form 16 header. Gate: No.
9. **Filing status u/s 139** — 139(1) default; 139(4) if past due date; 139(5) if revised; 139(8A) for ITR-U. Inputs: system clock + filing-type selection from case 2. Gate: Yes.
10. **Regime selection (old vs new)** — runs `tax_calc` for both regimes with extracted facts, picks the lower-tax one, **but always asks user to confirm** because this is a high-impact choice. Inputs: extracted facts + `tax_calc`. Gate: Yes, always.

#### Page: Gross Total Income — Salary schedule

11. **Fill Salary (Sec 17(1)) / Perquisites (17(2)) / Profits in lieu (17(3))** — from Form 16 Part B boxes with the same labels. Gate: No (matches source exactly).
12. **Standard deduction** — auto-fills ₹50,000 (old) or ₹75,000 (new, AY 2025-26), only if salary head is non-zero. Inputs: regime + salary. Gate: No.
13. **Exempt allowances (HRA / LTA / others)** — pulls Part B exemptions from Form 16; if HRA requires the three-limb calc, runs the calculator using rent paid (user asks for it if not in docs). Gate: Yes (if any calculator-derived value).

#### Page: Income from Other Sources / Capital Gains

14. **Interest income** — bank interest from AIS SFT-007 / SFT-016 or from bank interest certificates; flags any mismatch between docs and AIS as a card for the user. Gate: Yes on mismatch, No otherwise.
15. **Capital gains from equity / MF** — parses broker CAS, splits STCG vs LTCG, applies ₹1L LTCG exemption u/s 112A, populates Schedule CG rows. Gate: Yes (capital-gains are high-stakes).

#### Page: Deductions (Chapter VI-A)

16. **80C / 80CCC / 80CCD(1)** — aggregates PF (from Form 16), ELSS, LIC, PPF from investment proofs; hard-caps at ₹1.5L. Gate: No (values come straight from docs).
17. **80D medical insurance** — parses premium receipts; applies age-based caps (₹25k self / ₹50k parents-senior). Gate: No.
18. **80CCD(1B) NPS additional ₹50k / 80G donations / 80TTA interest** — each from the matching proof document. Gate: No.

#### Page: Tax Paid + Verification

19. **TDS from Form 16 / 16A / 26AS** — fills Schedule TDS rows (TAN, name, gross payment, TDS deducted) by reconciling Form 16 Part A with 26AS/AIS. Flags any row where the amount differs. Gate: Yes on reconciliation mismatch.
20. **Bank account for refund** — selects the pre-validated account flagged in the portal profile; if none is validated, the agent stops and walks the user through the validation flow instead of filling. Gate: Yes, always (refund destination).

### Shared mechanics for form-filling actions

- **New tools** on top of Phase 1–3:
  - `get_form_schema(page)` — wraps the existing DSL; returns the list of fillable fields with selectors + validation rules for the current portal page.
  - `propose_fill(thread_id, page, fields)` — LLM-called; agent returns an array of `{selector, value, source_citation, gate}` objects. The backend stores this as a "fill plan" row (there's already a `fill_plan.py` node stub in `agent/nodes/` for this).
  - `execute_fill_plan(thread_id, plan_id, confirmed_ids)` — emits the DSL ops to the extension via the existing websocket. Only emits ops whose `gate == "No"` OR whose id is in `confirmed_ids`.
  - `read_portal_field(selector)` — reads back what the portal now shows, for the post-write verification step.
  - `get_validation_errors()` — wraps the existing DSL op; fed back to the LLM so it can fix its own mistakes before clicking Continue.

- **User-confirmation UI**: every Gate=Yes field surfaces in the side panel as a diff card (`current value → proposed value`, plus the source citation). User taps Accept / Edit / Skip per row, or Accept All. The `execute_fill_plan` call only runs after the card is resolved.

- **Write-then-verify loop**:
  1. `get_form_schema` → `propose_fill` → show diff cards.
  2. User confirms.
  3. Backend emits DSL `fill` ops → extension writes → extension echoes success.
  4. Agent calls `read_portal_field` on each written field to confirm the portal accepted the value (the e-Filing portal occasionally rejects silently).
  5. Agent calls `get_validation_errors` → if any, loops back to propose_fill for just those fields.
  6. Only after the page is clean does the agent propose the Continue click.

- **Safety rails**:
  - Hard stop on any field the agent doesn't have a document-backed or calculator-backed source for. Don't guess PAN, DOB, amounts.
  - Every executed fill is logged to the existing `audit.py` service with `{thread_id, page, selector, value_hash, source_citation, confirmed_by_user, timestamp}`.
  - Refund bank account, regime choice, ITR form type, 44AB Yes, and any amount > ₹50k always require explicit confirmation, even if extracted from docs with high confidence.
  - The agent never clicks the final **Submit / E-verify** button. That remains a user action — by design, for legal/liability reasons.

### Phase mapping for form-fill work

Add a **Phase 2.5** between the Q&A phases and web search:

- **Phase 2.5 — Form-filling agent**
  - New tools: `get_form_schema`, `propose_fill`, `execute_fill_plan`, `read_portal_field`, `get_validation_errors`.
  - Wire the existing `fill_plan.py` and `execute_actions.py` node stubs into the runner (no more stubs).
  - Diff-card UI in the side panel for user confirmation.
  - Audit + replay test coverage for all 20 cases using the fixture thread from Phase 4.

### Acceptance for Phase 2.5

All 20 form-fill cases above pass an end-to-end replay test on a mock portal harness:
- The agent produces a correct fill plan from a fixture document bundle.
- Gate=No fields auto-execute; Gate=Yes fields are staged behind a confirmation card.
- After execution, `get_validation_errors` returns empty.
- The audit log contains one row per executed field with a traceable source citation.

---

## 8. Next step

Once this plan is approved, implementation begins with **Phase 0** in a feature branch. Smallest-possible PR: LLM client + runner + tool registry (empty) + replacing the `_build_agent_response` switchboard. The 40 Q&A cases plus the 20 form-fill cases then become the acceptance test suite.
