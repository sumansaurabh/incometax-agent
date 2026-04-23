-- Encrypted-document support.
--
-- documents.status gains two new string values (schema is untyped text, no enum change needed):
--   'awaiting_password'           : pipeline detected encryption, waiting on user unlock
--   'password_attempts_exhausted' : too many wrong passwords; user must re-upload
--
-- password_hint carries a short UI hint (e.g. 'upload_ais_pdf_instead' for encrypted JSON
-- variants we cannot yet decrypt server-side).

alter table documents
  add column if not exists password_hint text;

create table if not exists document_password_attempts (
  document_id uuid primary key references documents(id) on delete cascade,
  attempt_count integer not null default 0,
  last_attempt_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
