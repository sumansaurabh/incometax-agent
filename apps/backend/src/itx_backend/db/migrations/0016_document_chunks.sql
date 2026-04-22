create table if not exists document_chunks (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  thread_id text,
  version_no integer not null default 1,
  chunk_index integer not null,
  chunk_text text not null,
  page_number integer,
  section_name text,
  embedding_status text not null default 'pending',
  created_at timestamptz not null default now(),
  unique (document_id, version_no, chunk_index)
);

create index if not exists idx_document_chunks_thread on document_chunks(thread_id, created_at desc);
create index if not exists idx_document_chunks_document on document_chunks(document_id, version_no, chunk_index);
