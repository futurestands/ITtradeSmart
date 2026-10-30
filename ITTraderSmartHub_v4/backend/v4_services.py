"""V4 read-only crossover services with token hashing, pairing code enrollment, RBAC scopes, rate limiting, and security audit logging."""
import hashlib
import hmac
import os
import secrets
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite
from threading import RLock
from risk_engine import calculate_risk


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def finite_number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not minimum <= value <= maximum:
        raise ValueError('Invalid numeric field')
    return float(value)


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of a token for secure database storage."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class ContextStore:
    """Server-side state with SQLite persistence for hashed tokens, pairing codes, telemetry, alerts, and security audit logs."""
    def __init__(self, database_path=None):
        self.lock = RLock()
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")
        self.stress = None
        self.alerts = []
        self.devices = {}  # token_hash -> {device_id, device_name, created_at, expires_at, revoked, role}
        self.pairing_codes = {}  # code_hash -> {created_at, expires_at, used}
        self.audit_logs = []
        self.request_counts = defaultdict(list)  # token_hash -> list of timestamps
        self.enrollment_failures = defaultdict(list)  # client_ip -> list of failure timestamps
        self.seq = 0

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS telemetry (id INTEGER PRIMARY KEY CHECK(id=1), stress INTEGER NOT NULL, recorded_at TEXT NOT NULL, source TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS alerts (seq INTEGER PRIMARY KEY AUTOINCREMENT, service TEXT NOT NULL, severity TEXT NOT NULL, recorded_at TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS devices (device_id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked INTEGER DEFAULT 0, device_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'device')")
                db.execute("CREATE TABLE IF NOT EXISTS pairing_codes (code_hash TEXT PRIMARY KEY, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used INTEGER DEFAULT 0)")
                db.execute("CREATE TABLE IF NOT EXISTS auth_audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, event_type TEXT NOT NULL, client_ip TEXT, device_id TEXT, details TEXT)")

                # Safe schema migration check
                columns = [col[1] for col in db.execute("PRAGMA table_info(devices)").fetchall()]
                if 'token' in columns and 'token_hash' not in columns:
                    db.execute("ALTER TABLE devices RENAME TO legacy_devices")
                    db.execute("CREATE TABLE devices (device_id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked INTEGER DEFAULT 0, device_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'device')")

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                row = db.execute("SELECT stress, recorded_at, source FROM telemetry WHERE id=1").fetchone()
                if row:
                    self.stress = {"value": row[0], "recorded_at": row[1], "source": row[2]}
                for seq, sev, ts in db.execute("SELECT seq, severity, recorded_at FROM alerts ORDER BY seq DESC LIMIT 200").fetchall()[::-1]:
                    self.alerts.append({"event_id": f"evt-{seq}", "service": "infrastructure", "technical_severity": sev, "notification_priority": "NORMAL", "message": "Operational stress telemetry updated", "exposure_data_fresh": False, "recorded_at": ts})
                    self.seq = max(self.seq, seq)
                for dev_id, thash, created, exp, rev, dev_name, role in db.execute("SELECT device_id, token_hash, created_at, expires_at, revoked, device_name, role FROM devices").fetchall():
                    self.devices[thash] = {"device_id": dev_id, "device_name": dev_name, "created_at": created, "expires_at": exp, "revoked": bool(rev), "role": role}
                for chash, created, exp, used in db.execute("SELECT code_hash, created_at, expires_at, used FROM pairing_codes WHERE used=0").fetchall():
                    self.pairing_codes[chash] = {"created_at": created, "expires_at": exp, "used": bool(used)}

    def log_audit(self, event_type, client_ip=None, device_id=None, details=""):
        with self.lock:
            entry = {
                "timestamp": utcnow(),
                "event_type": event_type,
                "client_ip": client_ip or "unknown",
                "device_id": device_id or "unknown",
                "details": details
            }
            self.audit_logs.append(entry)
            self.audit_logs = self.audit_logs[-500:]
            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("INSERT INTO auth_audit (timestamp, event_type, client_ip, device_id, details) VALUES (?,?,?,?,?)",
                               (entry["timestamp"], event_type, entry["client_ip"], entry["device_id"], details))

    def generate_pairing_code(self, ttl_minutes=10, client_ip="127.0.0.1"):
        """Administrator creates a short-lived, one-time device pairing code."""
        with self.lock:
            code = f"PAIR-{secrets.randbelow(900000) + 100000}"
            chash = hash_token(code)
            now = datetime.now(timezone.utc)
            expires = (now + timedelta(minutes=ttl_minutes)).isoformat()

            self.pairing_codes[chash] = {
                "created_at": now.isoformat(),
                "expires_at": expires,
                "used": False
            }

            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("INSERT OR REPLACE INTO pairing_codes (code_hash, created_at, expires_at, used) VALUES (?,?,?,0)",
                               (chash, now.isoformat(), expires))

            self.log_audit("PAIRING_CODE_CREATED", client_ip, details=f"Created one-time code expiring in {ttl_minutes}m")
            return {"pairing_code": code, "expires_at": expires}

    def enroll_device(self, device_id, device_name, pairing_code, client_ip="127.0.0.1"):
        """Mobile client enrolls using an administrator-generated one-time pairing code."""
        with self.lock:
            # Check enrollment rate limiting: max 5 failures per 15 minutes
            now_ts = datetime.now(timezone.utc).timestamp()
            failures = [t for t in self.enrollment_failures[client_ip] if now_ts - t < 900]
            if len(failures) >= 5:
                self.log_audit("ENROLLMENT_RATE_LIMITED", client_ip, device_id, f"Blocked after {len(failures)} failures")
                raise ValueError("Too many failed enrollment attempts. Please wait 15 minutes.")

            if not device_id or not isinstance(device_id, str) or len(device_id) < 8:
                self.enrollment_failures[client_ip].append(now_ts)
                raise ValueError("Invalid device ID")

            chash = hash_token(pairing_code.strip())
            code_info = self.pairing_codes.get(chash)

            if not code_info or code_info["used"]:
                self.enrollment_failures[client_ip].append(now_ts)
                self.log_audit("ENROLLMENT_FAILED", client_ip, device_id, "Invalid or reused pairing code")
                raise ValueError("Invalid or used pairing code")

            expires_dt = datetime.fromisoformat(code_info["expires_at"])
            if datetime.now(timezone.utc) > expires_dt:
                self.enrollment_failures[client_ip].append(now_ts)
                self.log_audit("ENROLLMENT_FAILED", client_ip, device_id, "Expired pairing code")
                raise ValueError("Pairing code expired")

            # Mark code as used
            code_info["used"] = True
            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("UPDATE pairing_codes SET used=1 WHERE code_hash=?", (chash,))

            # Generate device token and store its cryptographic SHA-256 hash
            token = secrets.token_hex(32)
            thash = hash_token(token)
            now = datetime.now(timezone.utc)
            token_expires = (now + timedelta(hours=24)).isoformat()

            dev_info = {
                "device_id": device_id,
                "device_name": device_name or "Mobile Device",
                "created_at": now.isoformat(),
                "expires_at": token_expires,
                "revoked": False,
                "role": "device"
            }
            self.devices[thash] = dev_info

            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("INSERT OR REPLACE INTO devices (device_id, token_hash, created_at, expires_at, revoked, device_name, role) VALUES (?,?,?,?,0,?,'device')",
                               (device_id, thash, dev_info["created_at"], token_expires, dev_info["device_name"]))

            self.log_audit("DEVICE_ENROLLED", client_ip, device_id, f"Enrolled {dev_info['device_name']}")
            return {"status": "ENROLLED", "device_token": token, "expires_at": token_expires, "device_id": device_id}

    def renew_token(self, current_token, client_ip="127.0.0.1"):
        """Renews an active, non-expired device token."""
        thash = hash_token(current_token)
        with self.lock:
            dev_info = self.devices.get(thash)
            if not dev_info or dev_info["revoked"]:
                self.log_audit("RENEWAL_FAILED", client_ip, details="Invalid or revoked token")
                raise ValueError("Invalid or revoked token")

            expires_dt = datetime.fromisoformat(dev_info["expires_at"])
            if datetime.now(timezone.utc) > expires_dt:
                self.log_audit("RENEWAL_FAILED", client_ip, dev_info["device_id"], "Token expired")
                raise ValueError("Token expired")

            # Revoke old token
            dev_info["revoked"] = True

            # Issue new token
            new_token = secrets.token_hex(32)
            new_thash = hash_token(new_token)
            now = datetime.now(timezone.utc)
            new_expires = (now + timedelta(hours=24)).isoformat()

            new_dev_info = {
                "device_id": dev_info["device_id"],
                "device_name": dev_info["device_name"],
                "created_at": now.isoformat(),
                "expires_at": new_expires,
                "revoked": False,
                "role": dev_info["role"]
            }
            self.devices[new_thash] = new_dev_info

            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("UPDATE devices SET revoked=1 WHERE token_hash=?", (thash,))
                    db.execute("INSERT INTO devices (device_id, token_hash, created_at, expires_at, revoked, device_name, role) VALUES (?,?,?,?,0,?,?)",
                               (dev_info["device_id"], new_thash, new_dev_info["created_at"], new_expires, dev_info["device_name"], dev_info["role"]))

            self.log_audit("TOKEN_RENEWED", client_ip, dev_info["device_id"], "Issued fresh 24h token")
            return {"status": "RENEWED", "device_token": new_token, "expires_at": new_expires}

    def revoke_device(self, target_device_id, requesting_auth_info, client_ip="127.0.0.1"):
        """Revokes a device. Ordinary devices can only revoke their own session. Admin can revoke any device."""
        req_role = requesting_auth_info.get("role")
        req_device_id = requesting_auth_info.get("device_id")

        if req_role != "admin" and req_device_id != target_device_id:
            self.log_audit("REVOCATION_FORBIDDEN", client_ip, req_device_id, f"Attempted to revoke target device {target_device_id}")
            raise PermissionError("Ordinary devices cannot revoke other devices")

        with self.lock:
            revoked_count = 0
            for thash, info in list(self.devices.items()):
                if info["device_id"] == target_device_id and not info["revoked"]:
                    info["revoked"] = True
                    revoked_count += 1

            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("UPDATE devices SET revoked=1 WHERE device_id=?", (target_device_id,))

            self.log_audit("DEVICE_REVOKED", client_ip, target_device_id, f"Revoked by {req_role} ({req_device_id or 'admin'})")
            return {"status": "REVOKED", "target_device_id": target_device_id, "revoked_count": revoked_count}

    def verify_token(self, token, required_role="device", client_ip="127.0.0.1"):
        """Verifies access token, checks revocation, expiration, rate limiting, and RBAC role permissions."""
        master_secret = os.environ.get("SMARTHUB_API_TOKEN", "")
        if len(master_secret) >= 32 and hmac.compare_digest(token, master_secret):
            return True, "OK", {"role": "admin", "device_id": "admin-master"}

        thash = hash_token(token)
        with self.lock:
            if thash not in self.devices:
                self.log_audit("AUTH_FAILED", client_ip, details="Unknown token")
                return False, "Unauthorized: Unknown token", None

            info = self.devices[thash]
            if info["revoked"]:
                self.log_audit("AUTH_FAILED", client_ip, info["device_id"], "Token revoked")
                return False, "Unauthorized: Token revoked", None

            expires_dt = datetime.fromisoformat(info["expires_at"])
            if datetime.now(timezone.utc) > expires_dt:
                self.log_audit("AUTH_FAILED", client_ip, info["device_id"], "Token expired")
                return False, "Unauthorized: Token expired", None

            if required_role == "admin" and info["role"] != "admin":
                self.log_audit("ACCESS_FORBIDDEN", client_ip, info["device_id"], "Attempted admin action with device token")
                return False, "Forbidden: Administrator privileges required", None

            # Rate limiting: max 60 requests/min
            now_ts = datetime.now(timezone.utc).timestamp()
            timestamps = [t for t in self.request_counts[thash] if now_ts - t < 60]
            if len(timestamps) >= 60:
                self.log_audit("RATE_LIMIT_EXCEEDED", client_ip, info["device_id"], f"{len(timestamps)} req/min")
                return False, "Rate limit exceeded (max 60 req/min)", None

            timestamps.append(now_ts)
            self.request_counts[thash] = timestamps
            return True, "OK", dict(info)

    def set_stress(self, stress, source):
        if type(stress) is not int or not 0 <= stress <= 100:
            raise ValueError('Invalid stress index')
        if source != 'authorized_telemetry_agent':
            raise ValueError('Untrusted telemetry source')
        with self.lock:
            self.stress = {'value': stress, 'recorded_at': utcnow(), 'source': source}
            self.seq += 1
            event = {'event_id': f'evt-{self.seq}', 'service': 'infrastructure',
                     'technical_severity': 'HIGH' if stress >= 80 else 'MEDIUM' if stress >= 50 else 'INFO',
                     'notification_priority': 'NORMAL', 'message': 'Operational stress telemetry updated',
                     'exposure_data_fresh': False, 'recorded_at': self.stress['recorded_at']}
            self.alerts.append(event)
            self.alerts = self.alerts[-200:]
            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("INSERT OR REPLACE INTO telemetry (id,stress,recorded_at,source) VALUES (1,?,?,?)", (stress, self.stress["recorded_at"], source))
                    db.execute("INSERT INTO alerts (seq,service,severity,recorded_at) VALUES (?,?,?,?)", (self.seq, "infrastructure", event["technical_severity"], event["recorded_at"]))
            return dict(self.stress)

    def get_stress(self):
        with self.lock:
            return None if self.stress is None else dict(self.stress)

    def query_alerts(self, since_event_id=None, limit=20):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('Invalid alert limit')
        with self.lock:
            if since_event_id is not None:
                if not isinstance(since_event_id, str) or not since_event_id.startswith('evt-') or not since_event_id[4:].isdigit():
                    raise ValueError('Invalid cursor')
                cursor = int(since_event_id[4:])
                rows = [a for a in self.alerts if int(a['event_id'][4:]) > cursor]
            else:
                rows = self.alerts[-limit:]
            rows = rows[:limit]
            return {'server_time': utcnow(), 'alerts': [dict(a) for a in rows],
                    'next_cursor': rows[-1]['event_id'] if rows else since_event_id,
                    'persistence': 'sqlite' if self.database_path else 'volatile', 'exposure_source': 'not_connected'}

    def query_audit_logs(self, limit=50):
        with self.lock:
            return {"audit_logs": self.audit_logs[-limit:]}


def risk_context(body, store):
    baseline = finite_number(body.get('baseline_risk_pct'), 0.000001, 100)
    symbol = body.get('symbol')
    if not isinstance(symbol, str) or not 1 <= len(symbol) <= 32 or not all(x.isalnum() or x in '._-' for x in symbol):
        raise ValueError('Invalid symbol')
    if body.get('schema_version') != 1:
        raise ValueError('Unsupported schema version')
    stress = store.get_stress()

    if stress is None:
        return {'mode': 'advisory_only', 'status': 'UNAVAILABLE', 'effective_risk_pct': None,
                'reason_codes': ['SERVER_TELEMETRY_MISSING', 'MARKET_DATA_UNAVAILABLE', 'BEHAVIOR_DATA_UNAVAILABLE'],
                'data_fresh': False, 'policy_version': 'risk-v4.0'}
    recorded_at = datetime.fromisoformat(stress["recorded_at"])
    if datetime.now(timezone.utc) - recorded_at > timedelta(seconds=120):
        return {"mode": "advisory_only", "status": "UNAVAILABLE", "effective_risk_pct": None,
                "infrastructure_risk_ceiling_pct": None, "reason_codes": ["SERVER_TELEMETRY_STALE"],
                "data_fresh": False, "policy_version": "risk-v4.1"}
    return {'mode': 'advisory_only', 'status': 'UNAVAILABLE', 'effective_risk_pct': None,
            'infrastructure_risk_ceiling_pct': calculate_risk(1, baseline, stress['value']).effective_percent,
            'infrastructure_stress': stress['value'], 'reason_codes': ['MARKET_DATA_UNAVAILABLE', 'BEHAVIOR_DATA_UNAVAILABLE'],
            'data_fresh': False, 'policy_version': 'risk-v4.0'}


def research_request(body):
    if body.get('schema_version') != 1:
        raise ValueError('Unsupported schema version')
    outcome = body.get('outcome')
    if outcome not in ('rule_violation', 'realized_pnl', 'risk_escalation'):
        raise ValueError('Invalid outcome')
    try:
        start = datetime.fromisoformat(body['start_utc'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(body['end_utc'].replace('Z', '+00:00'))
    except (KeyError, AttributeError, ValueError):
        raise ValueError('Invalid date range')
    if start.tzinfo is None or end.tzinfo is None or not start < end or (end - start).days > 365:
        raise ValueError('Date range must be timezone aware and within 365 days')
    return {'status': 'UNAVAILABLE', 'analysis_type': 'observational', 'sample': None,
            'result': None, 'reason_codes': ['PERSISTENT_INCIDENT_HISTORY_MISSING', 'RECONSTRUCTED_TRADE_HISTORY_MISSING'],
            'policy_recommendation': 'NO_CHANGE'}
