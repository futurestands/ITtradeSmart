-- ====================================================================
-- ITTrader SmartHub v4 — Supabase PostgreSQL Database Migration Script
-- Project Reference: ydynjbjszjvhusdkiaou
-- Endpoint: https://ydynjbjszjvhusdkiaou.supabase.co
-- Connection String: postgresql://postgres:[PASSWORD]@db.ydynjbjszjvhusdkiaou.supabase.co:5432/postgres
-- ====================================================================

BEGIN;

-- 1. Infrastructure Telemetry Table
CREATE TABLE IF NOT EXISTS public.telemetry (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    stress INT NOT NULL CHECK (stress >= 0 AND stress <= 100),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    source TEXT NOT NULL DEFAULT 'authorized_telemetry_agent'
);

COMMENT ON TABLE public.telemetry IS 'Stores operational infrastructure stress index for ITTrader SmartHub v4.';

-- 2. Exposure-Aware Alerts Table
CREATE TABLE IF NOT EXISTS public.alerts (
    seq BIGSERIAL PRIMARY KEY,
    service TEXT NOT NULL DEFAULT 'infrastructure',
    technical_severity TEXT NOT NULL CHECK (technical_severity IN ('INFO', 'MEDIUM', 'HIGH', 'CRITICAL')),
    notification_priority TEXT NOT NULL DEFAULT 'NORMAL',
    message TEXT NOT NULL,
    exposure_data_fresh BOOLEAN NOT NULL DEFAULT FALSE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_alerts_seq_recorded ON public.alerts (seq DESC, recorded_at DESC);
COMMENT ON TABLE public.alerts IS 'Stores system and risk alert history with cursor pagination support.';

-- 3. Enrolled Devices & Short-Lived Access Tokens
CREATE TABLE IF NOT EXISTS public.devices (
    device_id TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    device_name TEXT NOT NULL DEFAULT 'Mobile Device'
);

CREATE INDEX IF NOT EXISTS idx_devices_token ON public.devices (token) WHERE revoked = FALSE;
COMMENT ON TABLE public.devices IS 'Stores enrolled mobile device UUIDs and short-lived access tokens.';

-- 4. Security & Authentication Audit Log
CREATE TABLE IF NOT EXISTS public.auth_audit (
    seq BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    event_type TEXT NOT NULL,
    client_ip TEXT,
    device_id TEXT,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_audit_timestamp ON public.auth_audit (timestamp DESC);
COMMENT ON TABLE public.auth_audit IS 'Audit trail for device enrollments, token revocations, and auth failures.';

-- ====================================================================
-- 5. Row Level Security (RLS) Policies
-- Protects tables from unauthorized anonymous client access
-- ====================================================================

ALTER TABLE public.telemetry ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_audit ENABLE ROW LEVEL SECURITY;

-- Allow service_role / authenticated server gateway full access
DROP POLICY IF EXISTS service_role_telemetry ON public.telemetry;
CREATE POLICY service_role_telemetry ON public.telemetry FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_alerts ON public.alerts;
CREATE POLICY service_role_alerts ON public.alerts FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_devices ON public.devices;
CREATE POLICY service_role_devices ON public.devices FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS service_role_auth_audit ON public.auth_audit;
CREATE POLICY service_role_auth_audit ON public.auth_audit FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMIT;
