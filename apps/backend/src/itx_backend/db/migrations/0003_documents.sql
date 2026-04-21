create table if not exists documents (
  id uuid primary key,
  thread_id text,
  file_name text not null,
  storage_uri text not null,
  sha256 text,
  mime text not null,
  byte_size bigint not null default 0,
  doc_type text not null,
  classification_confidence numeric not null default 0,
  status text not null,
  uploaded_at timestamptz not null default now(),
  parsed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists document_versions (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  version_no integer not null,
  storage_uri text not null,
  sha256 text,
  created_at timestamptz not null default now(),
  unique (document_id, version_no)
);

create table if not exists document_extractions (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  extractor_name text not null,
  extractor_version text not null,
  raw_json jsonb not null,
  normalized_json jsonb not null default '{}'::jsonb,
  confidence numeric not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists document_entities (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  page_no integer not null default 1,
  entity_type text not null,
  value text not null,
  normalized text,
  confidence numeric not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_documents_thread_id on documents(thread_id);
create index if not exists idx_documents_status on documents(status);
create index if not exists idx_document_extractions_document_id on document_extractions(document_id, created_at desc);
create index if not exists idx_document_entities_document_id on document_entities(document_id);