"""Read-only MT5 monitoring API with Pipnex smart lot sizing, prop firm drawdown shield, and authoritative ITTrader SmartHub v5 Bot Control."""
import hmac
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from flask import Flask, request, jsonify
from risk_engine import calculate_risk, calculate_pipnex_lot_size, calculate_prop_firm_rules
from trade_analysis import analyze_deals
from v4_services import ContextStore, risk_context, research_request
from bot import BotController, BacktestEngine, MarketDataManager, TrendFollowingMACrossoverStrategy

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
_mt5_lock = Lock()
_v4_store = ContextStore()
_bot = BotController(database_path=os.environ.get("SMARTHUB_STATE_DB"))


def check_auth(req, required_role="device"):
    auth_header = req.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False, "Missing Bearer token", None
    token = auth_header[7:].strip()
    if not token or len(token) < 32:
        return False, "Invalid token format", None
    return _v4_store.verify_token(token, required_role=required_role, client_ip=req.remote_addr)


@app.before_request
def require_authentication():
    exempt_paths = ('/api/v4/telemetry/stress', '/api/v4/device/enroll', '/health')
    if request.path in exempt_paths:
        return None

    required_role = "admin" if request.path in ('/api/v4/auth/audit', '/api/v4/admin/pairing-code', '/api/v5/bot/mode') else "device"
    ok, err_msg, auth_info = check_auth(request, required_role=required_role)
    if not ok:
        status_code = 403 if "Forbidden" in err_msg else 401
        return jsonify({'error': err_msg}), status_code

    request.auth_info = auth_info


# ====================================================================
# V5 AUTOMATED TRADING BOT ENDPOINTS (Authoritative Broker Feed)
# ====================================================================

@app.get('/api/v5/bot/status')
def bot_status():
    return jsonify(_bot.get_status()), 200


@app.post('/api/v5/bot/mode')
def set_bot_mode():
    body = request.get_json(silent=True) or {}
    mode = body.get('mode', 'OFF')
    passcode = body.get('admin_passcode', '')
    try:
        status = _bot.set_mode(mode, passcode)
        return jsonify(status), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403


@app.post('/api/v5/bot/emergency-stop')
def bot_emergency_stop():
    status = _bot.emergency_stop()
    return jsonify(status), 200


@app.post('/api/v5/bot/tick')
def bot_tick():
    """Triggers automated bot cycle using authoritative broker feed. Client-injected prices are prohibited."""
    stress = _v4_store.get_stress()
    stress_val = stress['value'] if stress else 0
    try:
        res = _bot.tick(stress_val)
        return jsonify(res), 200
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


@app.post('/api/v5/bot/backtest')
def bot_backtest():
    body = request.get_json(silent=True) or {}
    symbol = body.get('symbol', 'BTCUSD')
    num_bars = int(body.get('num_bars', 200))

    md = MarketDataManager(database_path=os.environ.get("SMARTHUB_STATE_DB"))
    candles = md.fetch_real_mt5_candles(symbol, timeframe_str="H1", num_bars=num_bars)
    strat = TrendFollowingMACrossoverStrategy()
    bt_engine = BacktestEngine(10000.0)

    bt_res = bt_engine.run_backtest(strat, candles, symbol)
    mc_res = bt_engine.run_monte_carlo(bt_res)

    return jsonify({
        "backtest_result": bt_res.__dict__,
        "monte_carlo_result": mc_res
    }), 200


# ====================================================================
# PIPNEX SMART CALCULATOR & PROP FIRM ENDPOINTS
# ====================================================================

@app.post('/api/v4/pipnex/calculator')
def pipnex_calculator():
    body = request.get_json(silent=True) or {}
    try:
        balance = float(body.get('balance', 10000))
        risk_pct = float(body.get('risk_pct', 1.0))
        stop_loss_pips = float(body.get('stop_loss_pips', 20.0))
        symbol = body.get('symbol', 'BTCUSD')

        res = calculate_pipnex_lot_size(balance, risk_pct, stop_loss_pips, symbol)
        return jsonify(res), 200
    except (ValueError, TypeError) as e:
        return jsonify({'error': str(e)}), 400


@app.post('/api/v4/pipnex/prop-firm')
def pipnex_prop_firm():
    body = request.get_json(silent=True) or {}
    try:
        current_equity = float(body.get('current_equity', 10000))
        initial_balance = float(body.get('initial_balance', 10000))
        daily_starting_equity = float(body.get('daily_starting_equity', 10000))

        res = calculate_prop_firm_rules(current_equity, initial_balance, daily_starting_equity)
        return jsonify(res), 200
    except (ValueError, TypeError) as e:
        return jsonify({'error': str(e)}), 400


@app.post('/api/v4/admin/pairing-code')
def admin_pairing_code():
    body = request.get_json(silent=True) or {}
    ttl = body.get('ttl_minutes', 10)
    try:
        ttl = int(ttl)
        if not 1 <= ttl <= 60:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid ttl_minutes (1-60)'}), 400

    res = _v4_store.generate_pairing_code(ttl_minutes=ttl, client_ip=request.remote_addr)
    return jsonify(res), 200


@app.post('/api/v4/device/enroll')
def enroll_device():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get('device_id') or not body.get('pairing_code'):
        return jsonify({'error': 'Device ID and pairing_code are required'}), 400

    if 'enrollment_secret' in body or 'api_token' in body:
        return jsonify({'error': 'Master secrets must never be submitted from mobile devices. Use one-time pairing codes.'}), 400

    try:
        res = _v4_store.enroll_device(body['device_id'], body.get('device_name', ''), body['pairing_code'], request.remote_addr)
        return jsonify(res), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.post('/api/v4/device/renew')
def renew_token():
    auth_header = request.headers.get('Authorization', '')
    token = auth_header[7:].strip()
    try:
        res = _v4_store.renew_token(token, client_ip=request.remote_addr)
        return jsonify(res), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.post('/api/v4/device/revoke')
def revoke_device():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body.get('device_id'):
        return jsonify({'error': 'device_id is required'}), 400

    target_id = body['device_id']
    try:
        res = _v4_store.revoke_device(target_id, request.auth_info, client_ip=request.remote_addr)
        return jsonify(res), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403


@app.get('/api/v4/auth/audit')
def auth_audit():
    return jsonify(_v4_store.query_audit_logs(limit=50))


@app.post('/api/v4/telemetry/stress')
def ingest_stress():
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
        return jsonify({**decision.__dict__, 'mode': 'advisory_only'})
    except (KeyError, ValueError, TypeError, OverflowError):
        return jsonify({'error': 'Invalid risk parameters'}), 400


@app.post('/analyze')
def analyze_psychology():
    body = request.get_json(silent=True) or {}
    if any(key in body for k in ('password', 'login', 'server')):
        return jsonify({'error': 'Broker credentials must never be submitted to this API'}), 400

    try:
        login = int(os.environ['MT5_LOGIN'])
        password = os.environ['MT5_INVESTOR_PASSWORD']
        server = os.environ['MT5_SERVER']
        if not login or not password or not server:
            raise ValueError('MT5 credentials incomplete')
    except (KeyError, ValueError):
        return jsonify({'error': 'MT5 not configured on gateway host'}), 503

    try:
        import MetaTrader5 as mt5
    except ImportError:
        return jsonify({'error': 'MT5 library unavailable; Windows host required'}), 503

    with _mt5_lock:
        initialized = False
        try:
            initialized = bool(mt5.initialize(login=login, password=password, server=server))
            if not initialized:
                return jsonify({'error': 'MT5 terminal connection failed'}), 503

            account = mt5.account_info()
            if account is None:
                return jsonify({'error': 'Account state unavailable'}), 503

            if bool(getattr(account, 'trade_allowed', False)) or bool(getattr(account, 'trade_expert', False)):
                return jsonify({'error': 'Gateway requires a read-only investor session'}), 403

            now = datetime.now(timezone.utc)
            deals = mt5.history_deals_get(now - timedelta(days=7), now)
            if deals is None:
                return jsonify({'error': 'MT5 history retrieval failed'}), 503

            return jsonify(analyze_deals(deals))
        except Exception:
            app.logger.exception('MT5 request failed')
            return jsonify({'error': 'MT5 operation failed'}), 503
        finally:
            if initialized:
                mt5.shutdown()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
