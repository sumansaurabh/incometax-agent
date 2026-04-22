alter table auth_users
  add column if not exists password_hash text,
  add column if not exists password_updated_at timestamptz;
