create table if not exists year_over_year_comparisons (
  id uuid primary key,
  thread_id text not null,
  user_id text not null,
  current_assessment_year text,
  prior_thread_id text,
  prior_assessment_year text,
  comparison_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_year_over_year_thread_created on year_over_year_comparisons(thread_id, created_at desc);

create table if not exists next_ay_checklists (
  id uuid primary key,
  thread_id text not null unique,
  user_id text not null,
  current_assessment_year text,
  target_assessment_year text not null,
  checklist_json jsonb not null default '[]'::jsonb,
  summary_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists notice_response_preparations (
  id uuid primary key,
  thread_id text not null,
  user_id text not null,
  notice_type text not null default '143(1)',
  assessment_year text,
  source_storage_uri text,
  extracted_json jsonb not null default '{}'::jsonb,
  explanation_md text not null default '',
  suggested_response_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_notice_preparations_thread_created on notice_response_preparations(thread_id, created_at desc);

create table if not exists refund_status_snapshots (
  id uuid primary key,
  thread_id text not null,
  user_id text not null,
  assessment_year text,
  status text not null,
  refund_amount numeric,
  portal_ref text,
  issued_at timestamptz,
  processed_at timestamptz,
  refund_mode text,
  bank_masked text,
  source text not null default 'manual',
  observation_json jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

create index if not exists idx_refund_snapshots_thread_observed on refund_status_snapshots(thread_id, observed_at desc);