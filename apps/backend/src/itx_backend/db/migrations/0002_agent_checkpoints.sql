create table if not exists agent_checkpoints (
  id bigserial primary key,
  thread_id text not null,
  current_node text not null,
  state_json jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_checkpoints_thread_id
  on agent_checkpoints (thread_id, id desc);