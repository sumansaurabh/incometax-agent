-- Minimal bootstrap migration; full schema defined in docs/DATA_MODEL.md
create table if not exists filing_audit_trail (
  id uuid primary key,
  ay_id text not null,
  event text not null,
  payload jsonb,
  rule_version text not null,
  adapter_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
