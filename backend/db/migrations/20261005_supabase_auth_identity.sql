ALTER TABLE users ADD COLUMN supabase_user_id TEXT;
ALTER TABLE users ADD COLUMN account_scope TEXT;
ALTER TABLE users ADD COLUMN auth_linked_at TEXT;

UPDATE users
SET account_scope = CASE
    WHEN username = 'admin' AND role = 'admin' THEN 'platform'
    WHEN role = 'driver' THEN 'driver'
    ELSE 'carrier'
END
WHERE account_scope IS NULL OR account_scope = '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_supabase_user_id
ON users (supabase_user_id)
WHERE supabase_user_id IS NOT NULL AND supabase_user_id <> '';
