create table if not exists chat_messages (
  id uuid primary key,
  thread_id text not null,
  role text not null,
  content text not null,
  message_type text not null default 'text',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_chat_messages_thread_created on chat_messages(thread_id, created_at desc);
