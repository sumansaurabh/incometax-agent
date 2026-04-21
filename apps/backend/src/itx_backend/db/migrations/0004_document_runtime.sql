alter table if exists document_versions
  add column if not exists reason text;

alter table if exists document_extractions
  add column if not exists version_no integer not null default 1;

alter table if exists document_entities
  add column if not exists version_no integer not null default 1;

create table if not exists document_pages (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  version_no integer not null default 1,
  page_no integer not null,
  text text,
  ocr_used boolean not null default false,
  ocr_confidence numeric,
  created_at timestamptz not null default now()
);

create table if not exists document_tables (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  version_no integer not null default 1,
  page_no integer not null,
  rows jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists document_jobs (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  thread_id text,
  doc_type text not null,
  queue_name text not null default 'document_processing',
  status text not null,
  attempts integer not null default 0,
  last_error text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

create index if not exists idx_document_pages_document_version on document_pages(document_id, version_no, page_no);
create index if not exists idx_document_tables_document_version on document_tables(document_id, version_no, page_no);
create index if not exists idx_document_jobs_status_created on document_jobs(status, created_at);
create index if not exists idx_document_jobs_document on document_jobs(document_id, created_at desc);