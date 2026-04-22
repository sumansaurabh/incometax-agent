create table if not exists portal_snapshots (
  thread_id text primary key,
  current_url text,
  page_title text,
  page_type text,
  focused_field text,
  fields jsonb not null default '[]'::jsonb,
  errors jsonb not null default '[]'::jsonb,
  raw jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_portal_snapshots_updated on portal_snapshots(updated_at desc);
