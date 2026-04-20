# Data Model (Postgres)

Postgres is the system of record. Keep **raw extraction**, **normalized interpretation**, and **portal-entered value** as separate columns so we can always answer: *what did the document say? what did the system infer? what got entered?*

Conventions:

- All tables: `id uuid pk`, `created_at`, `updated_at`, `tenant_id` (row-level isolation).
- Row-level security (RLS) enforced by `tenant_id` and `user_id`.
- Sensitive blobs live in object storage; Postgres stores only pointers + hashes.
- Every claim row carries `rule_version` and `source_evidence_id`.

## 1. Identity & sessions

```sql
users (
  id uuid pk,
  email citext unique,
  phone_masked text,
  pan_hash text,                      -- hashed, never plaintext
  created_at, updated_at, deleted_at
)

devices (
  id uuid pk,
  user_id fk users,
  fingerprint text,
  platform text, ua text,
  first_seen, last_seen
)

browser_sessions (
  id uuid pk,
  user_id fk, device_id fk,
  extension_version text,
  started_at, ended_at,
  revoked boolean default false
)

portal_sessions (
  id uuid pk,
  user_id fk,
  browser_session_id fk,
  portal_host text,                   -- must be incometax.gov.in
  started_at, last_activity_at,
  terminated_reason text
)
```

## 2. Documents

```sql
documents (
  id uuid pk,
  user_id fk, thread_id fk,
  storage_uri text,                   -- object-store key
  sha256 bytea,
  mime text, byte_size bigint,
  doc_type text,                      -- ais|tis|form16|form16a|salary_slip|...
  classification_confidence numeric,
  status text,                        -- uploaded|scanned|parsed|failed
  uploaded_at, parsed_at
)

document_versions (
  id uuid pk, document_id fk,
  version int,
  storage_uri text, sha256 bytea,
  reason text
)

document_pages (
  id uuid pk, document_id fk,
  page_no int,
  text text,
  ocr_used boolean,
  ocr_confidence numeric
)

document_extractions (
  id uuid pk, document_id fk,
  extractor_name text, extractor_version text,
  raw_json jsonb,
  confidence numeric,
  created_at
)

document_tables (
  id uuid pk, document_id fk, page_no int,
  rows jsonb                          -- [[cell, cell, ...], ...]
)

document_entities (
  id uuid pk, document_id fk, page_no int,
  entity_type text,                   -- PAN|TAN|AMOUNT|SECTION|EMPLOYER
  value text, normalized text,
  bbox jsonb, confidence numeric
)
```

## 3. Tax model (canonical facts)

```sql
tax_profiles (
  id uuid pk, user_id fk,
  pan_hash text, name_masked text,
  dob date,
  residential_status text,
  updated_at
)

assessment_years (
  id uuid pk, user_id fk,
  ay text,                             -- e.g., AY2025-26
  fy text,
  filing_status text                   -- draft|filled|submitted|verified|archived
)

income_items (
  id uuid pk, ay_id fk,
  head text,                           -- salary|hp|cg|os|business
  employer text, section text,
  raw_value numeric, normalized_value numeric,
  source_evidence_id fk,
  rule_version text,
  human_verified boolean
)

deduction_items (
  id uuid pk, ay_id fk,
  section text,                        -- 80C|80D|80G|80TTA...
  sub_limit text,
  raw_value numeric, normalized_value numeric,
  applied_value numeric,               -- after caps
  source_evidence_id fk,
  rule_version text, human_verified boolean
)

tax_payments (
  id uuid pk, ay_id fk,
  type text,                           -- tds|tcs|advance|self_assessment
  bsr_code text, challan_no text,
  amount numeric, deduction_month date,
  source_evidence_id fk
)

capital_gain_entries (
  id uuid pk, ay_id fk,
  asset_class text, holding text,      -- stcg|ltcg
  isin text, qty numeric,
  buy_date date, buy_value numeric,
  sell_date date, sell_value numeric,
  section_111a_112a_flag text,
  source_evidence_id fk
)

rental_entries (
  id uuid pk, ay_id fk,
  property_label text, gross_rent numeric,
  municipal_tax numeric, interest_on_loan numeric,
  source_evidence_id fk
)

form16_entries (
  id uuid pk, ay_id fk, document_id fk,
  employer text, tan text,
  gross_salary numeric, exempt_allowances numeric,
  tds numeric, period_from date, period_to date
)

ais_entries (
  id uuid pk, ay_id fk, document_id fk,
  category text,                       -- TDS|TCS|SFT|Taxes Paid|Demand-Refund|Other
  description text, amount numeric,
  info_source text, user_feedback text
)

tis_entries (
  id uuid pk, ay_id fk, document_id fk,
  head text, processed_value numeric, derived_value numeric
)
```

## 4. Agent state

```sql
agent_threads (
  id uuid pk, user_id fk, ay_id fk,
  status text,                         -- running|paused|awaiting_user|awaiting_portal|done|failed
  current_node text,
  created_at, updated_at
)

agent_checkpoints (                    -- LangGraph-compatible
  thread_id fk, checkpoint_id text,
  state jsonb, metadata jsonb,
  created_at,
  primary key (thread_id, checkpoint_id)
)

agent_runs (
  id uuid pk, thread_id fk,
  started_at, ended_at,
  outcome text, error text
)

tool_calls (
  id uuid pk, run_id fk,
  tool_name text, input jsonb, output jsonb,
  model_name text, tokens_in int, tokens_out int,
  latency_ms int, retries int,
  requires_approval boolean, approved boolean
)

action_proposals (
  id uuid pk, thread_id fk,
  dsl jsonb,                           -- structured fill plan
  sensitivity text, reason text,
  created_at, expires_at
)

action_executions (
  id uuid pk, proposal_id fk,
  started_at, ended_at,
  success boolean, error text,
  dom_snapshot_before uri, dom_snapshot_after uri
)
```

## 5. Portal mapping

```sql
portal_pages (
  id uuid pk,
  page_key text,                       -- e.g., salary-schedule
  detector_version text,
  adapter_version text
)

portal_field_definitions (
  id uuid pk, portal_page_id fk,
  canonical_key text,                  -- maps to tax-schema
  label_regex text, selector_hints jsonb,
  value_type text, required boolean
)

portal_field_observations (
  id uuid pk, portal_page_id fk,
  captured_at, dom_snapshot_uri text,
  observed_label text, observed_selector text,
  match_confidence numeric
)

field_fill_history (
  id uuid pk, thread_id fk,
  field_def_id fk,
  value_entered text,
  source_evidence_id fk, rule_version text,
  filled_at, result text                -- ok|validation_error|selector_miss
)

validation_errors (
  id uuid pk, thread_id fk,
  page_key text, field text,
  message text, parsed_reason text,
  captured_at
)
```

## 6. Compliance & audit

```sql
consents (
  id uuid pk, user_id fk,
  purpose text,                         -- upload_ais|fill_portal|regime_compare|...
  scope jsonb,
  granted_at, revoked_at,
  text_hash bytea                       -- hash of exact consent text shown
)

approvals (
  id uuid pk, thread_id fk,
  kind text,                            -- fill_batch|submit|regime_switch|bank_change|everify
  proposal_id fk,
  user_decision text, decided_at,
  ip_masked inet, ua text
)

security_events (
  id uuid pk, user_id fk,
  type text,                            -- anomaly|rate_limit|phish_block|...
  detail jsonb, created_at
)

data_access_logs (
  id uuid pk, actor text,               -- user|agent|admin
  resource_type text, resource_id uuid,
  action text, reason text,
  created_at
)

filing_audit_trail (
  id uuid pk, ay_id fk,
  event text,                           -- fact_added|field_filled|mismatch_flagged|submitted|everified
  payload jsonb,
  rule_version text, adapter_version text,
  created_at
)
```

## 7. Output artifacts

```sql
draft_returns (
  id uuid pk, ay_id fk,
  itr_type text, regime text,
  payload jsonb,                         -- full canonical return
  generated_at
)

submission_summaries (
  id uuid pk, draft_return_id fk,
  summary_md text,
  total_income numeric, total_deductions numeric,
  taxable_income numeric, tax_payable numeric,
  refund_due numeric,
  mismatches jsonb
)

everification_status (
  id uuid pk, ay_id fk,
  method text,                           -- aadhaar_otp|evc|netbank|dsc
  status text, verified_at,
  portal_ref text
)

filed_return_artifacts (
  id uuid pk, ay_id fk,
  ack_no text,
  itr_v_storage_uri text,
  json_export_uri text,
  filed_at
)
```

## 8. Indexes & partitioning

- Partition `document_pages`, `document_extractions`, `tool_calls`, `filing_audit_trail` by `created_at` month.
- B-tree indexes on `(user_id, ay_id)`, `(thread_id, created_at)`, `(document_id, page_no)`.
- GIN indexes on `raw_json`, `state`, `payload`.

## 9. Retention policy

| Class | Retention |
|---|---|
| Uploaded raw documents | 30 days post filing, then purge unless user pins |
| Extracted canonical facts | 7 years (statutory) |
| Agent checkpoints | 30 days post thread closure |
| Tool-call transcripts | 90 days, PII-redacted |
| Audit trail | 7 years |
| DOM snapshots | 7 days unless tied to an incident |
