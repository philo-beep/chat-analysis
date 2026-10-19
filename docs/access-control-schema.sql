-- Generated from a fresh initialized SQLite database. Structural reference only.
-- Existing databases must use database.init_db() migrations, not this script.
PRAGMA foreign_keys = ON;

CREATE TABLE access_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at INTEGER NOT NULL, user_id INTEGER REFERENCES users(id),
        feature TEXT NOT NULL, path TEXT NOT NULL, method TEXT NOT NULL,
        status_code INTEGER NOT NULL, duration_ms INTEGER NOT NULL);

CREATE TABLE auth_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL, revoked_at INTEGER);

CREATE TABLE permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL, created_at INTEGER NOT NULL);

CREATE TABLE records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            , source_input TEXT, source_image TEXT, source_transcript TEXT NOT NULL DEFAULT '', owner_id INTEGER REFERENCES users(id));

CREATE TABLE role_permissions (
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE RESTRICT,
            created_at INTEGER NOT NULL, PRIMARY KEY(role_id, permission_id));

CREATE TABLE roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, created_at INTEGER NOT NULL);

CREATE TABLE user_roles (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
            created_at INTEGER NOT NULL, PRIMARY KEY(user_id, role_id));

CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(username) BETWEEN 3 AND 64),
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);

CREATE INDEX idx_events_feature ON access_events(feature, created_at);

CREATE INDEX idx_events_time ON access_events(created_at, id);

CREATE INDEX idx_records_owner ON records(owner_id, id DESC);

CREATE INDEX ix_auth_sessions_expiry ON auth_sessions(expires_at);

CREATE INDEX ix_auth_sessions_user ON auth_sessions(user_id, expires_at);

CREATE INDEX ix_role_permissions_permission ON role_permissions(permission_id, role_id);

CREATE INDEX ix_user_roles_role ON user_roles(role_id, user_id);
