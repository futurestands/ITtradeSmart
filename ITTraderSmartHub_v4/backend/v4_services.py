"""V4 read-only crossover services. Unavailable data yields no risk approval."""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from threading import RLock
import sqlite3
import os
from datetime import timedelta
from risk_engine import calculate_risk


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def finite_number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not minimum <= value <= maximum:
        raise ValueError('Invalid numeric field')
    return float(value)


class ContextStore:
    """Ephemeral server-only state; never authoritative after restart."""
    def __init__(self, database_path=None):
        self.lock = RLock()
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")
        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS telemetry (id INTEGER PRIMARY KEY CHECK(id=1), stress INTEGER NOT NULL, recorded_at TEXT NOT NULL, source TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS alerts (seq INTEGER PRIMARY KEY AUTOINCREMENT, service TEXT NOT NULL, severity TEXT NOT NULL, recorded_at TEXT NOT NULL)")
        self.stress = None
        self.alerts = []
        self.seq = 0
        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                row = db.execute("SELECT stress, recorded_at, source FROM telemetry WHERE id=1").fetchone()
                if row:
                    self.stress = {"value":row[0], "recorded_at":row[1], "source":row[2]}
                for seq, sev, ts in db.execute("SELECT seq, severity, recorded_at FROM alerts ORDER BY seq DESC LIMIT 200").fetchall()[::-1]:
                    self.alerts.append({"event_id":f"evt-{seq}", "service":"infrastructure", "technical_severity":sev, "notification_priority":"NORMAL", "message":"Operational stress telemetry updated", "exposure_data_fresh":False, "recorded_at":ts})
                    self.seq = max(self.seq, seq)

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
                    db.execute("INSERT OR REPLACE INTO telemetry (id,stress,recorded_at,source) VALUES (1,?,?,?)", (stress,self.stress["recorded_at"],source))
                    db.execute("INSERT INTO alerts (seq,service,severity,recorded_at) VALUES (?,?,?,?)", (self.seq,"infrastructure",event["technical_severity"],event["recorded_at"]))
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


def risk_context(body, store):
    baseline = finite_number(body.get('baseline_risk_pct'), 0.000001, 100)
    symbol = body.get('symbol')
    if not isinstance(symbol, str) or not 1 <= len(symbol) <= 32 or not all(x.isalnum() or x in '._-' for x in symbol):
        raise ValueError('Invalid symbol')
    if body.get('schema_version') != 1:
        raise ValueError('Unsupported schema version')
    stress = store.get_stress()
    # Never accept mobile-supplied stress scores, exposure, or volatility as trusted data.
    if stress is None:
        return {'mode': 'advisory_only', 'status': 'UNAVAILABLE', 'effective_risk_pct': None,
                'reason_codes': ['SERVER_TELEMETRY_MISSING', 'MARKET_DATA_UNAVAILABLE', 'BEHAVIOR_DATA_UNAVAILABLE'],
                'data_fresh': False, 'policy_version': 'risk-v4.0'}
    recorded_at = datetime.fromisoformat(stress["recorded_at"])
    if datetime.now(timezone.utc) - recorded_at > timedelta(seconds=120):
        return {"mode":"advisory_only", "status":"UNAVAILABLE", "effective_risk_pct":None,
                "infrastructure_risk_ceiling_pct":None, "reason_codes":["SERVER_TELEMETRY_STALE"],
                "data_fresh":False, "policy_version":"risk-v4.1"}
    # Risk fusion requires server-verified volatility + behavior, not yet implemented.
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
    # Do not claim statistical results until persistent paired histories exist.
    return {'status': 'UNAVAILABLE', 'analysis_type': 'observational', 'sample': None,
            'result': None, 'reason_codes': ['PERSISTENT_INCIDENT_HISTORY_MISSING', 'RECONSTRUCTED_TRADE_HISTORY_MISSING'],
            'policy_recommendation': 'NO_CHANGE'}
