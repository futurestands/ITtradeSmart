-- v1.1 FRESH INSTALL REVIEW ONLY. v1 has never been applied to Neon.
-- No HTTP/import/deployment path executes this file.
-- Resource: smarthub-phase3-preview; physical PostgreSQL database: neondb.
-- Project: winter-hat-40889380; branch: phase3-auth-development
-- (br-autumn-scene-bcqp4rjv); endpoint: ep-winter-cake-bcffwgio.
-- Reverify this mapping in authenticated provider metadata before execution.
-- Never migrate main (br-red-butterfly-bc69ov3c / ep-cold-hall-bcb1xvqr).
-- A database name alone cannot establish project, branch or endpoint identity.
-- Abort preflight on any existing schema/role; do not adopt unknown objects.
BEGIN;
-- Fail before DDL unless connected to the verified physical database identifier.
-- Provider identity verification is an additional mandatory external gate.
DO $target_gate$
BEGIN
 IF pg_catalog.current_database() <> 'neondb' THEN
   RAISE EXCEPTION 'Unexpected database identity; migration refused';
 END IF;
END;
$target_gate$;
CREATE SCHEMA smarthub_cloud_auth;
CREATE ROLE smarthub_cloud_runtime NOLOGIN NOINHERIT;
CREATE ROLE smarthub_cloud_operator NOLOGIN NOINHERIT;
-- Dedicated private login identity remains DISABLED until separate bootstrap.
-- No owner/operator membership, password, or LOGIN activation in this migration.
CREATE ROLE smarthub_cloud_preview_login NOLOGIN NOINHERIT;
GRANT smarthub_cloud_runtime TO smarthub_cloud_preview_login WITH ADMIN FALSE;
GRANT smarthub_cloud_runtime TO smarthub_cloud_preview_login WITH INHERIT FALSE;
GRANT smarthub_cloud_runtime TO smarthub_cloud_preview_login WITH SET TRUE;

CREATE TABLE smarthub_cloud_auth.devices (
 id TEXT PRIMARY KEY, name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 128),
 role TEXT NOT NULL DEFAULT 'device' CHECK (role IN ('device','admin')),
 revoked BOOLEAN NOT NULL DEFAULT FALSE,
 created_at BIGINT NOT NULL DEFAULT floor(extract(epoch FROM statement_timestamp()))::bigint
);
CREATE TABLE smarthub_cloud_auth.sessions (
 access_hash TEXT PRIMARY KEY CHECK (length(access_hash)=64),
 refresh_hash TEXT UNIQUE NOT NULL CHECK (length(refresh_hash)=64),
 device_id TEXT NOT NULL REFERENCES smarthub_cloud_auth.devices(id),
 access_until BIGINT NOT NULL, refresh_until BIGINT NOT NULL,
 CHECK (access_until < refresh_until)
);
CREATE INDEX cloud_sessions_device ON smarthub_cloud_auth.sessions(device_id);
CREATE TABLE smarthub_cloud_auth.enrollment (
 code_hash TEXT PRIMARY KEY CHECK (length(code_hash)=64),
 expires_at BIGINT NOT NULL, used BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE smarthub_cloud_auth.rate_limits (
 scope TEXT NOT NULL CHECK (scope IN ('enrollment','access')),
 identity_hash TEXT NOT NULL CHECK (length(identity_hash)=64),
 window_start BIGINT NOT NULL CHECK (window_start % 60=0),
 expires_at BIGINT NOT NULL CHECK (expires_at=window_start+60),
 count INTEGER NOT NULL CHECK (count >= 1 AND
   ((scope='enrollment' AND count<=11) OR (scope='access' AND count<=121))),
 PRIMARY KEY (scope, identity_hash, window_start)
);
CREATE INDEX cloud_rate_expiry ON smarthub_cloud_auth.rate_limits(expires_at);
CREATE TABLE smarthub_cloud_auth.audit (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 occurred_at BIGINT NOT NULL, event TEXT NOT NULL,
 principal_hash TEXT NOT NULL CHECK (length(principal_hash)=64)
);

REVOKE ALL ON SCHEMA smarthub_cloud_auth FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA smarthub_cloud_auth FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA smarthub_cloud_auth FROM PUBLIC;
GRANT USAGE ON SCHEMA smarthub_cloud_auth TO smarthub_cloud_runtime, smarthub_cloud_operator;

-- No table-wide INSERT/UPDATE: role, revoked-at-creation and timestamps use DB defaults.
GRANT SELECT(id,role,revoked), INSERT(id,name), UPDATE(revoked)
 ON smarthub_cloud_auth.devices TO smarthub_cloud_runtime;
GRANT SELECT, INSERT, DELETE ON smarthub_cloud_auth.sessions TO smarthub_cloud_runtime;
GRANT SELECT, INSERT, UPDATE(used) ON smarthub_cloud_auth.enrollment TO smarthub_cloud_runtime;
GRANT SELECT, INSERT, UPDATE(count) ON smarthub_cloud_auth.rate_limits TO smarthub_cloud_runtime;
GRANT INSERT(occurred_at,event,principal_hash) ON smarthub_cloud_auth.audit TO smarthub_cloud_runtime;
GRANT USAGE ON SEQUENCE smarthub_cloud_auth.audit_id_seq TO smarthub_cloud_runtime, smarthub_cloud_operator;

-- Offline operator only: administrator bootstrap/rotation, audit reads, maintenance.
-- Never grant this role to the web login or store an operator credential in Vercel.
GRANT SELECT, INSERT, UPDATE ON smarthub_cloud_auth.devices TO smarthub_cloud_operator;
GRANT SELECT, INSERT, DELETE ON smarthub_cloud_auth.sessions TO smarthub_cloud_operator;
GRANT SELECT, INSERT, UPDATE ON smarthub_cloud_auth.enrollment TO smarthub_cloud_operator;
GRANT SELECT, DELETE ON smarthub_cloud_auth.rate_limits TO smarthub_cloud_operator;
GRANT SELECT, INSERT(occurred_at,event,principal_hash) ON smarthub_cloud_auth.audit TO smarthub_cloud_operator;

ALTER TABLE smarthub_cloud_auth.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE smarthub_cloud_auth.devices FORCE ROW LEVEL SECURITY;
CREATE POLICY devices_runtime_read ON smarthub_cloud_auth.devices
 FOR SELECT TO smarthub_cloud_runtime USING (TRUE);
CREATE POLICY devices_runtime_insert ON smarthub_cloud_auth.devices
 FOR INSERT TO smarthub_cloud_runtime WITH CHECK (role='device' AND revoked=FALSE);
CREATE POLICY devices_runtime_revoke ON smarthub_cloud_auth.devices
 FOR UPDATE TO smarthub_cloud_runtime USING (role='device')
 WITH CHECK (role='device' AND revoked=TRUE);
CREATE POLICY devices_operator ON smarthub_cloud_auth.devices
 FOR ALL TO smarthub_cloud_operator USING (TRUE) WITH CHECK (TRUE);

ALTER TABLE smarthub_cloud_auth.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE smarthub_cloud_auth.sessions FORCE ROW LEVEL SECURITY;
-- Shared web role may validate existing privately-bootstrapped administrator tokens.
-- It cannot mint, rotate or delete an administrator's sessions.
CREATE POLICY sessions_runtime_read ON smarthub_cloud_auth.sessions
 FOR SELECT TO smarthub_cloud_runtime USING (TRUE);
CREATE POLICY sessions_runtime_insert ON smarthub_cloud_auth.sessions
 FOR INSERT TO smarthub_cloud_runtime WITH CHECK (EXISTS (
   SELECT 1 FROM smarthub_cloud_auth.devices d
   WHERE d.id=device_id AND d.role='device' AND d.revoked=FALSE));
CREATE POLICY sessions_runtime_delete ON smarthub_cloud_auth.sessions
 FOR DELETE TO smarthub_cloud_runtime USING (EXISTS (
   SELECT 1 FROM smarthub_cloud_auth.devices d
   WHERE d.id=device_id AND d.role='device'));
CREATE POLICY sessions_operator ON smarthub_cloud_auth.sessions
 FOR ALL TO smarthub_cloud_operator USING (TRUE) WITH CHECK (TRUE);
COMMIT;
