-- REVIEW ONLY. Apply explicitly to an approved dedicated preview database.
-- No migration runs on import, startup, deployment or an HTTP request.
BEGIN;
CREATE SCHEMA IF NOT EXISTS smarthub_cloud_auth;
-- A non-login runtime role cannot authenticate until an approved private
-- bootstrap step assigns its generated password and enables LOGIN.
CREATE ROLE smarthub_cloud_runtime NOLOGIN;
CREATE TABLE smarthub_cloud_auth.devices (
 id TEXT PRIMARY KEY, name TEXT NOT NULL,
 role TEXT NOT NULL CHECK (role IN ('device','admin')),
 revoked BOOLEAN NOT NULL DEFAULT FALSE, created_at BIGINT NOT NULL
);
CREATE TABLE smarthub_cloud_auth.sessions (
 access_hash TEXT PRIMARY KEY, refresh_hash TEXT UNIQUE NOT NULL,
 device_id TEXT NOT NULL REFERENCES smarthub_cloud_auth.devices(id),
 access_until BIGINT NOT NULL, refresh_until BIGINT NOT NULL
);
CREATE INDEX cloud_sessions_device ON smarthub_cloud_auth.sessions(device_id);
CREATE TABLE smarthub_cloud_auth.enrollment (
 code_hash TEXT PRIMARY KEY, expires_at BIGINT NOT NULL, used BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE smarthub_cloud_auth.rate_limits (
 bucket TEXT PRIMARY KEY, count INTEGER NOT NULL
);
CREATE TABLE smarthub_cloud_auth.audit (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 occurred_at BIGINT NOT NULL, event TEXT NOT NULL, principal_hash TEXT NOT NULL
);
REVOKE ALL ON SCHEMA smarthub_cloud_auth FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA smarthub_cloud_auth FROM PUBLIC;
GRANT USAGE ON SCHEMA smarthub_cloud_auth TO smarthub_cloud_runtime;
GRANT SELECT, INSERT, UPDATE ON smarthub_cloud_auth.devices TO smarthub_cloud_runtime;
GRANT SELECT, INSERT, DELETE ON smarthub_cloud_auth.sessions TO smarthub_cloud_runtime;
GRANT SELECT, INSERT, UPDATE ON smarthub_cloud_auth.enrollment TO smarthub_cloud_runtime;
GRANT SELECT, INSERT, UPDATE ON smarthub_cloud_auth.rate_limits TO smarthub_cloud_runtime;
GRANT INSERT ON smarthub_cloud_auth.audit TO smarthub_cloud_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA smarthub_cloud_auth TO smarthub_cloud_runtime;
COMMIT;
