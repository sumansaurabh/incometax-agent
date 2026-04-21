create table if not exists replay_snapshots (
  snapshot_id text primary key,
  thread_id text not null,
  page_type text not null,
  dom_html text not null,
  url text not null,
  metadata jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now()
);

create index if not exists idx_replay_snapshots_thread_captured on replay_snapshots(thread_id, captured_at desc);

create table if not exists replay_runs (
  run_id text primary key,
  snapshot_id text not null references replay_snapshots(snapshot_id) on delete cascade,
  thread_id text not null,
  success boolean not null,
  mismatches jsonb not null default '[]'::jsonb,
  executed_at timestamptz not null default now()
);

create index if not exists idx_replay_runs_thread_executed on replay_runs(thread_id, executed_at desc);