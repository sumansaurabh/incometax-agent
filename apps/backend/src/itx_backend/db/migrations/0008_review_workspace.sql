create table if not exists review_handoffs (
  id uuid primary key,
  thread_id text not null,
  requested_by_user_id text not null,
  support_mode text not null,
  status text not null default 'prepared',
  reason text,
  reasons_json jsonb not null default '[]'::jsonb,
  checklist_json jsonb not null default '[]'::jsonb,
  summary_json jsonb not null default '{}'::jsonb,
  package_storage_uri text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_review_handoffs_thread on review_handoffs(thread_id, created_at desc);
create index if not exists idx_review_handoffs_requester on review_handoffs(requested_by_user_id, created_at desc);