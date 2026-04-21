create table if not exists review_access_grants (
  id uuid primary key,
  thread_id text not null,
  owner_user_id text not null,
  reviewer_email text not null,
  reviewer_user_id text,
  status text not null default 'active',
  scope jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  accepted_at timestamptz,
  revoked_at timestamptz
);

create unique index if not exists idx_review_access_grants_thread_reviewer on review_access_grants(thread_id, reviewer_email);
create index if not exists idx_review_access_grants_reviewer_status on review_access_grants(reviewer_email, status, created_at desc);

create table if not exists reviewer_signoffs (
  id uuid primary key,
  thread_id text not null,
  approval_key text not null references approvals(approval_key) on delete cascade,
  proposal_id uuid references action_proposals(id) on delete set null,
  owner_user_id text not null,
  reviewer_email text not null,
  reviewer_user_id text,
  status text not null default 'pending_reviewer',
  request_note text,
  reviewer_note text,
  client_note text,
  client_consent_key text unique,
  details_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  client_decided_at timestamptz
);

create unique index if not exists idx_reviewer_signoffs_approval_key on reviewer_signoffs(approval_key);
create index if not exists idx_reviewer_signoffs_thread_created on reviewer_signoffs(thread_id, created_at desc);
create index if not exists idx_reviewer_signoffs_reviewer_status on reviewer_signoffs(reviewer_email, status, created_at desc);