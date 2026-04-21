create table if not exists action_proposals (
  id uuid primary key,
  thread_id text not null,
  proposal_type text not null,
  dsl jsonb not null,
  sensitivity text,
  reason text,
  created_at timestamptz not null default now(),
  expires_at timestamptz
);

create table if not exists action_executions (
  id uuid primary key,
  proposal_id uuid references action_proposals(id) on delete cascade,
  thread_id text not null,
  execution_kind text not null default 'fill',
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  success boolean not null default false,
  error text,
  portal_state_before jsonb,
  portal_state_after jsonb,
  results_json jsonb not null default '{}'::jsonb
);

create table if not exists approvals (
  id uuid primary key,
  thread_id text not null,
  kind text not null,
  proposal_id uuid references action_proposals(id) on delete cascade,
  approval_key text not null,
  description text,
  consent_text text,
  status text not null,
  action_ids jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz,
  decided_at timestamptz,
  user_decision text,
  response_hash text,
  rejection_reason text,
  decision_payload jsonb
);

create unique index if not exists idx_approvals_approval_key on approvals(approval_key);
create index if not exists idx_approvals_thread_created on approvals(thread_id, created_at desc);

create table if not exists field_fill_history (
  id uuid primary key,
  thread_id text not null,
  proposal_id uuid references action_proposals(id) on delete set null,
  execution_id uuid references action_executions(id) on delete cascade,
  page_key text,
  field_id text not null,
  field_label text,
  selector text,
  value_before text,
  value_entered text,
  observed_value text,
  source_evidence_key text,
  source_document text,
  rule_version text,
  filled_at timestamptz not null default now(),
  result text not null
);

create index if not exists idx_field_fill_history_thread_filled on field_fill_history(thread_id, filled_at desc);

create table if not exists validation_errors (
  id uuid primary key,
  thread_id text not null,
  execution_id uuid references action_executions(id) on delete cascade,
  page_key text,
  field text,
  message text not null,
  parsed_reason text,
  captured_at timestamptz not null default now()
);

create index if not exists idx_validation_errors_thread_captured on validation_errors(thread_id, captured_at desc);