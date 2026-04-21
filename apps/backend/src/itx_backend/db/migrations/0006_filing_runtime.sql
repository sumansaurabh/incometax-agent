create table if not exists consents (
  id uuid primary key,
  thread_id text not null,
  user_id text not null,
  purpose text not null,
  approval_key text not null,
  scope jsonb not null default '{}'::jsonb,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  text_hash bytea not null,
  response_hash text
);

create unique index if not exists idx_consents_approval_key on consents(approval_key);
create index if not exists idx_consents_thread_granted on consents(thread_id, granted_at desc);

create table if not exists draft_returns (
  id uuid primary key,
  thread_id text not null,
  itr_type text not null,
  regime text,
  payload jsonb not null,
  generated_at timestamptz not null default now()
);

create index if not exists idx_draft_returns_thread_generated on draft_returns(thread_id, generated_at desc);

create table if not exists submission_summaries (
  id uuid primary key,
  thread_id text not null,
  draft_return_id uuid references draft_returns(id) on delete cascade,
  summary_json jsonb not null default '{}'::jsonb,
  summary_md text not null,
  total_income numeric not null default 0,
  total_deductions numeric not null default 0,
  taxable_income numeric not null default 0,
  tax_payable numeric not null default 0,
  refund_due numeric not null default 0,
  mismatches jsonb not null default '[]'::jsonb,
  generated_at timestamptz not null default now()
);

create index if not exists idx_submission_summaries_thread_generated on submission_summaries(thread_id, generated_at desc);

create table if not exists everification_status (
  id uuid primary key,
  thread_id text not null,
  handoff_id text not null,
  method text not null,
  status text not null,
  target_url text,
  portal_ref text,
  handoff_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  verified_at timestamptz
);

create unique index if not exists idx_everification_status_handoff on everification_status(handoff_id);
create index if not exists idx_everification_status_thread_created on everification_status(thread_id, created_at desc);

create table if not exists filed_return_artifacts (
  id uuid primary key,
  thread_id text not null,
  ack_no text,
  itr_v_storage_uri text,
  json_export_uri text,
  evidence_bundle_uri text,
  summary_storage_uri text,
  filed_at timestamptz not null default now(),
  artifact_manifest jsonb not null default '{}'::jsonb
);

create index if not exists idx_filed_return_artifacts_thread_filed on filed_return_artifacts(thread_id, filed_at desc);

create table if not exists revision_threads (
  id uuid primary key,
  base_thread_id text not null,
  revision_thread_id text not null unique,
  revision_number integer not null,
  reason text,
  prior_return_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_revision_threads_base_created on revision_threads(base_thread_id, created_at desc);