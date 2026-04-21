create table if not exists auth_users (
  id uuid primary key,
  email text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists auth_devices (
  id uuid primary key,
  user_id uuid not null references auth_users(id) on delete cascade,
  device_id text not null unique,
  device_name text,
  user_agent text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  revoked_at timestamptz
);

create index if not exists idx_auth_devices_user_seen on auth_devices(user_id, last_seen_at desc);

create table if not exists auth_sessions (
  id uuid primary key,
  user_id uuid not null references auth_users(id) on delete cascade,
  device_id text not null references auth_devices(device_id) on delete cascade,
  access_secret_hash text not null,
  refresh_secret_hash text not null,
  access_expires_at timestamptz not null,
  refresh_expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  last_refreshed_at timestamptz,
  revoked_at timestamptz
);

create index if not exists idx_auth_sessions_user_created on auth_sessions(user_id, created_at desc);
create index if not exists idx_auth_sessions_device_created on auth_sessions(device_id, created_at desc);

create table if not exists purge_jobs (
  id uuid primary key,
  thread_id text not null,
  reason text not null,
  requested_by text not null,
  status text not null default 'queued',
  requested_at timestamptz not null default now(),
  due_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  details jsonb not null default '{}'::jsonb
);

create index if not exists idx_purge_jobs_thread_requested on purge_jobs(thread_id, requested_at desc);
create index if not exists idx_purge_jobs_status_due on purge_jobs(status, due_at asc);