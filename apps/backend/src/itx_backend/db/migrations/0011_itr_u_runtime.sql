create table if not exists itr_u_threads (
  id uuid primary key,
  base_thread_id text not null,
  itr_u_thread_id text unique,
  status text not null default 'awaiting_escalation',
  reason_code text not null,
  reason_detail text not null default '',
  base_ack_no text,
  eligibility_json jsonb not null default '{}'::jsonb,
  escalation_confirmed_at timestamptz,
  escalation_confirmed_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_itr_u_threads_base_created on itr_u_threads(base_thread_id, created_at desc);
create index if not exists idx_itr_u_threads_itr_u_thread on itr_u_threads(itr_u_thread_id) where itr_u_thread_id is not null;
