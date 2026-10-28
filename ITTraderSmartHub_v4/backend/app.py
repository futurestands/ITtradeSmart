"""Read-only MT5 monitoring API. Bind to loopback; use TLS private reverse proxy/VPN."""
import hmac
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from flask import Flask, request, jsonify
from risk_engine import calculate_risk
from trade_analysis import analyze_deals
from v4_services import ContextStore, risk_context, research_request

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
_mt5_lock = Lock()
_v4_store = ContextStore()


def authorized(req):
    expected = os.environ.get('SMARTHUB_API_TOKEN', '')
    provided = req.headers.get('Authorization', '')
    return len(expected) >= 32 and hmac.compare_digest(provided, 'Bearer ' + expected)


@app.before_request
def require_authentication():
    if request.path == '/api/v4/telemetry/stress':
        return None  # Endpoint validates its own separate agent token.
    if not authorized(request):
        return jsonify({'error': 'Unauthorized'}), 401


@app.post('/api/v4/telemetry/stress')
def ingest_stress():
    # Distinct credential scope: this endpoint must never be callable by a mobile token.
    import hmac
    agent_token = os.environ.get('SMARTHUB_TELEMETRY_TOKEN', '')
    provided = request.headers.get('X-Telemetry-Token', '')
    if len(agent_token) < 32 or not hmac.compare_digest(provided, agent_token):
        return jsonify({'error': 'Telemetry agent not authorized'}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {'stress_index', 'source'}:
        return jsonify({'error': 'Invalid telemetry payload'}), 400
    try:
        return jsonify(_v4_store.set_stress(data['stress_index'], data['source']))
    except ValueError:
        return jsonify({'error': 'Invalid telemetry payload'}), 400


@app.post('/api/v4/risk/context')
def v4_risk_context():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or any(k in body for k in ('password', 'login', 'server', 'stress_index')):
        return jsonify({'error': 'Invalid risk request'}), 400
    try:
        return jsonify(risk_context(body, _v4_store))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid risk parameters'}), 400


@app.post('/api/v4/alerts/query')
def v4_alerts():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or body.get('schema_version') != 1 or body.get('console') not in ('it', 'trading', 'combined'):
        return jsonify({'error': 'Invalid alert request'}), 400
    try:
        return jsonify(_v4_store.query_alerts(body.get('since_event_id'), body.get('limit', 20)))
    except ValueError:
        return jsonify({'error': 'Invalid alert request'}), 400


@app.post('/api/v4/research/incident-impact')
def v4_research():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({'error': 'Invalid research request'}), 400
    try:
        return jsonify(research_request(body))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid research request'}), 400


@app.get('/health')
def health():
    return jsonify({'status': 'ok', 'mt5_checked': False})


@app.post('/risk')
def risk():
    try:
        body = request.get_json(silent=True) or {}
        decision = calculate_risk(float(body['balance']), float(body['baseline_percent']),
                                  body['stress_index'])
        return jsonify({**decision.__dict__, 'mode':'advisory_only'})
    except (KeyError, ValueError, TypeError, OverflowError):
        return jsonify({'error':'Invalid risk parameters'}), 400


@app.post('/analyze')
def analyze_psychology():
    body = request.get_json(silent=True) or {}
    if any(key in body for key in ('password', 'login', 'server')):
        return jsonify({'error':'Broker credentials must never be submitted to this API'}), 400
    try:
        login = int(os.environ['MT5_LOGIN'])
        password = os.environ['MT5_INVESTOR_PASSWORD']
        server = os.environ['MT5_SERVER']
        if not login or not password or not server:
            raise ValueError('MT5 credentials incomplete')
    except (KeyError, ValueError):
        return jsonify({'error':'MT5 not configured on gateway host'}), 503
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return jsonify({'error':'MT5 library unavailable; Windows host required'}), 503
    with _mt5_lock:
        initialized = False
        try:
            initialized = bool(mt5.initialize(login=login, password=password, server=server))
            if not initialized:
                return jsonify({'error':'MT5 terminal connection failed'}), 503
            account = mt5.account_info()
            if account is None:
                return jsonify({'error':'Account state unavailable'}), 503
            # Investor mode is typically read-only; reject sessions that advertise trade permission.
            if bool(getattr(account, 'trade_allowed', False)) or bool(getattr(account, 'trade_expert', False)):
                return jsonify({'error':'Gateway requires a read-only investor session'}), 403
            now = datetime.now(timezone.utc)
            deals = mt5.history_deals_get(now - timedelta(days=7), now)
            if deals is None:
                return jsonify({'error':'MT5 history retrieval failed'}), 503
            return jsonify(analyze_deals(deals))
        except Exception:
            app.logger.exception('MT5 request failed')
            return jsonify({'error':'MT5 operation failed'}), 503
        finally:
            if initialized:
                mt5.shutdown()


if __name__ == '__main__':
    # Deliberately never expose the Flask dev server to the network.
    app.run(host='127.0.0.1', port=5000, debug=False)
