"""V4 read-only crossover services with device enrollment, token revocation, rate limiting, and security audit logging."""
import hmac
import os
import sqlite3
import secrets
from collections import defaultdict
from dataclasses import dataclass
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


class ContextStore:
    """Server-side state with optional SQLite persistence for telemetry, alerts, enrolled devices, and security audit logs."""
    def __init__(self, database_path=None):
        self.lock = RLock()
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")
        self.stress = None
        self.alerts = []
        self.devices = {}  # token -> {device_id, device_name, created_at, expires_at, revoked}
        self.audit_logs = []
        self.request_counts = defaultdict(list)  # token -> list of timestamps
        self.seq = 0

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS telemetry (id INTEGER PRIMARY KEY CHECK(id=1), stress INTEGER NOT NULL, recorded_at TEXT NOT NULL, source TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS alerts (seq INTEGER PRIMARY KEY AUTOINCREMENT, service TEXT NOT NULL, severity TEXT NOT NULL, recorded_at TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS devices (device_id TEXT PRIMARY KEY, token TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked INTEGER DEFAULT 0, device_name TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS auth_audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, event_type TEXT NOT NULL, client_ip TEXT, device_id TEXT, details TEXT)")

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                row = db.execute("SELECT stress, recorded_at, source FROM telemetry WHERE id=1").fetchone()
                if row:
                    self.stress = {"value": row[0], "recorded_at": row[1], "source": row[2]}
                for seq, sev, ts in db.execute("SELECT seq, severity, recorded_at FROM alerts ORDER BY seq DESC LIMIT 200").fetchall()[::-1]:
                    self.alerts.append({"event_id": f"evt-{seq}", "service": "infrastructure", "technical_severity": sev, "notification_priority": "NORMAL", "message": "Operational stress telemetry updated", "exposure_data_fresh": False, "recorded_at": ts})
                    self.seq = max(self.seq, seq)
                for dev_id, tok, created, exp, rev, dev_name in db.execute("SELECT device_id, token, created_at, expires_at, revoked, device_name FROM devices").fetchall():
                    self.devices[tok] = {"device_id": dev_id, "device_name": dev_name, "created_at": created, "expires_at": exp, "revoked": bool(rev)}

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

    def enroll_device(self, device_id, device_name, enrollment_secret, client_ip="127.0.0.1"):
        master_secret = os.environ.get("SMARTHUB_API_TOKEN", "")
        if len(master_secret) < 32 or not hmac.compare_digest(enrollment_secret, master_secret):
            self.log_audit("ENROLLMENT_FAILED", client_ip, device_id, "Invalid enrollment secret")
            raise ValueError("Invalid enrollment secret")

        if not device_id or not isinstance(device_id, str) or len(device_id) < 8:
            raise ValueError("Invalid device ID")

        with self.lock:
            token = secrets.token_hex(32)
            now = datetime.now(timezone.utc)
            expires = (now + timedelta(hours=24)).isoformat()
            dev_info = {
                "device_id": device_id,
                "device_name": device_name or "Mobile Device",
                "created_at": now.isoformat(),
                "expires_at": expires,
                "revoked": False
            }
            self.devices[token] = dev_info

            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("INSERT OR REPLACE INTO devices (device_id, token, created_at, expires_at, revoked, device_name) VALUES (?,?,?,?,0,?)",
                               (device_id, token, dev_info["created_at"], expires, dev_info["device_name"]))

            self.log_audit("DEVICE_ENROLLED", client_ip, device_id, f"Enrolled {dev_info['device_name']}")
            return {"status": "ENROLLED", "device_token": token, "expires_at": expires, "device_id": device_id}

    def revoke_device(self, device_id, client_ip="127.0.0.1"):
        with self.lock:
            revoked_count = 0
            for token, info in list(self.devices.items()):
                if info["device_id"] == device_id and not info["revoked"]:
                    info["revoked"] = True
                    revoked_count += 1
            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("UPDATE devices SET revoked=1 WHERE device_id=?", (device_id,))
            self.log_audit("DEVICE_REVOKED", client_ip, device_id, f"Revoked {revoked_count} active tokens")
            return {"status": "REVOKED", "revoked_count": revoked_count}

    def verify_token(self, token, client_ip="127.0.0.1"):
        master_secret = os.environ.get("SMARTHUB_API_TOKEN", "")
        # Accept master token for admin/tests
        if len(master_secret) >= 32 and hmac.compare_digest(token, master_secret):
            return True

        with self.lock:
            if token not in self.devices:
                self.log_audit("AUTH_FAILED", client_ip, details="Unknown token")
                return False

            info = self.devices[token]
            if info["revoked"]:
                self.log_audit("AUTH_FAILED", client_ip, info["device_id"], "Token revoked")
                return False

            expires = datetime.fromisoformat(info["expires_at"])
            if datetime.now(timezone.utc) > expires:
                self.log_audit("AUTH_FAILED", client_ip, info["device_id"], "Token expired")
                return False

            # Rate limiting: max 60 requests per minute
            now_ts = datetime.now(timezone.utc).timestamp()
            timestamps = [t for t in self.request_counts[token] if now_ts - t < 60]
            if len(timestamps) >= 60:
                self.log_audit("RATE_LIMIT_EXCEEDED", client_ip, info["device_id"], f"{len(timestamps)} req/min")
                return False

            timestamps.append(now_ts)
            self.request_counts[token] = timestamps
            return True

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
