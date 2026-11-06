-- REVIEW ONLY: offline operator role, not a web route or startup hook.
-- At most 1000 expired rows per run, after a five-minute in-flight safety grace.
-- The web connection's 10-second idle-transaction timeout is shorter than this grace.
-- Append one operator audit event when rows are removed; never modify/delete audit.
-- END HEADER
WITH expired AS (
 SELECT scope, identity_hash, window_start
 FROM smarthub_cloud_auth.rate_limits
 WHERE expires_at <= floor(extract(epoch FROM statement_timestamp()))::bigint - 300
 ORDER BY expires_at, scope, identity_hash, window_start
 LIMIT 1000
), removed AS (
 DELETE FROM smarthub_cloud_auth.rate_limits r USING expired e
 WHERE r.scope=e.scope AND r.identity_hash=e.identity_hash AND r.window_start=e.window_start
 AND r.expires_at <= floor(extract(epoch FROM statement_timestamp()))::bigint - 300
 RETURNING 1
), logged AS (
 INSERT INTO smarthub_cloud_auth.audit(occurred_at,event,principal_hash)
 SELECT floor(extract(epoch FROM statement_timestamp()))::bigint,
        'EXPIRED_RATE_BUCKETS_PURGED',
        encode(sha256(convert_to(session_user::text,'UTF8')),'hex')
 WHERE EXISTS (SELECT 1 FROM removed)
 RETURNING 1
)
SELECT (SELECT count(*) FROM removed) AS expired_buckets_removed,
       (SELECT count(*) FROM logged) AS audit_events_appended;
