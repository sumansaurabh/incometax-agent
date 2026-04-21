create table if not exists analytics_events (
  id bigserial primary key,
  event_type text not null,
  stage text not null,
  thread_id text not null,
  payload jsonb not null default '{}'::jsonb,
  ts timestamptz not null default now()
);

create index if not exists idx_analytics_events_thread_ts on analytics_events(thread_id, ts asc);
create index if not exists idx_analytics_events_stage on analytics_events(stage);
create index if not exists idx_analytics_events_type on analytics_events(event_type);
