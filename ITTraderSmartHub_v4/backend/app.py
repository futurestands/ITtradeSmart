"""Read-only MT5 monitoring API with strict admin authorization on all v5 bot endpoints, local Windows-side MT5 provider quote ingestion, and fail-closed risk checks."""
import hmac
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from flask import Flask, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge
from risk_engine import calculate_risk, calculate_pipnex_lot_size, calculate_prop_firm_rules
from trade_analysis import analyze_deals
from v4_services import ContextStore, risk_context, research_request
from bot import BotController, BacktestEngine, MarketDataManager, TrendFollowingMACrossoverStrategy
from ai_lab_adapter import AILabAdapter
from nas100_research_status import read_progress_snapshot
from nas100_research_preview import synthetic_preview
from mt5_account_registry import (read_mt5_accounts, upsert_mt5_profile, delete_mt5_profile, ProfileConfigError)
from ai_contract import ContractError, strict_json

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
_mt5_lock = Lock()
_v4_store = ContextStore()
_bot = BotController(database_path=os.environ.get("SMARTHUB_STATE_DB"))
_ai_lab = AILabAdapter()


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

    # Ordinary Android monitoring tokens (device scope) CANNOT trigger v5 bot endpoints. Admin role required.
    is_v5_bot = request.path.startswith('/api/v5/bot/')
    required_role = "admin" if is_v5_bot or request.path in ('/api/v4/auth/audit', '/api/v4/admin/pairing-code') else "device"

    ok, err_msg, auth_info = check_auth(request, required_role=required_role)
    if not ok:
        status_code = 403 if "Forbidden" in err_msg else 401
        return jsonify({'error': err_msg}), status_code

    request.auth_info = auth_info


# ====================================================================
# V5 AUTOMATED TRADING BOT ENDPOINTS (Strict Admin Authorization)
# ====================================================================

# Monitoring-device authorization applies; these queries have no execution route.
@app.get('/api/v5/ai/status')
def ai_status():
    return jsonify(_ai_lab.status()), 200


@app.get('/api/v5/ai/research-progress')
def ai_research_progress():
    """Device-authenticated, read-only synthetic report summary; no model execution."""
    response = jsonify(read_progress_snapshot())
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response, 200


@app.get('/api/v5/nas100/research-preview')
def nas100_synthetic_research_preview():
    """Device-authenticated prototype, disabled unless explicitly opted in locally."""
    if os.environ.get('SMARTHUB_SYNTHETIC_PREVIEW_ENABLED') != '1':
        response = jsonify({'status': 'DISABLED', 'decision': 'NO_TRADE'})
        response.status_code = 503
    elif request.args or request.get_data():
        response = jsonify({'error': 'This fixed synthetic preview accepts no inputs', 'decision': 'NO_TRADE'})
        response.status_code = 400
    else:
        response = jsonify(synthetic_preview())
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@app.get('/api/v5/mt5/accounts')
def mt5_registered_accounts():
    """Device-authenticated read-only MT5 aliases. NOT broker connections."""
    response = jsonify(read_mt5_accounts())
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response, 200


def _account_profile_write_allowed():
    """Explicit server-side opt-in + enrolled device + local loopback only.

    No trade, account-identity, server, or credentials can be written here.
    """
    return (os.environ.get("SMARTHUB_ACCOUNT_PROFILE_EDITING") == "1"
            and request.remote_addr in ("127.0.0.1", "::1"))


@app.post('/api/v5/mt5/accounts')
def save_mt5_account_profile():
    if not _account_profile_write_allowed():
        return jsonify({"error": "Broker profile editing not enabled on Windows Gateway"}), 403
    if not request.is_json:
        return jsonify({"error": "Expected JSON broker profile"}), 400
    try:
        profile = strict_json(request.get_data(cache=False))
        result = upsert_mt5_profile(profile)
    except RequestEntityTooLarge:
        return jsonify({"error": "Request too large"}), 413
    except (ContractError, ProfileConfigError, OSError):
        return jsonify({"error": "Broker profile could not be saved; check safe fields and local configuration"}), 400
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response, 200


@app.delete('/api/v5/mt5/accounts/<account_id>')
def remove_mt5_account_profile(account_id):
    if not _account_profile_write_allowed():
        return jsonify({"error": "Broker profile editing not enabled on Windows Gateway"}), 403
    try:
        result = delete_mt5_profile(account_id)
    except (ProfileConfigError, OSError):
        return jsonify({"error": "Broker profile could not be removed"}), 400
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response, 200


@app.post('/api/v5/ai/advisory')
def ai_advisory():
    try:
        if not request.is_json:
            raise ContractError('INVALID_REQUEST')
        payload = strict_json(request.get_data(cache=False))
        return jsonify(_ai_lab.advisory(payload)), 200
    except RequestEntityTooLarge:
        return jsonify({'error': 'Request body too large'}), 413
    except ContractError:
        return jsonify({'error': 'Invalid advisory v1 request'}), 400

@app.get('/api/v5/bot/status')
def bot_status():
    return jsonify(_bot.get_status()), 200


@app.post('/api/v5/bot/mode')
def set_bot_mode():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('mode', 'OFF'), str):
        return jsonify({'error': 'Invalid bot mode request'}), 400
    mode = body.get('mode', 'OFF')
    passcode = body.get('admin_passcode', '')
    try:
        status = _bot.set_mode(mode, passcode)
        return jsonify(status), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except RuntimeError as e:
        return jsonify({'error': str(e), 'bot_status': _bot.get_status()}), 503


@app.post('/api/v5/bot/emergency-stop')
def bot_emergency_stop():
    status = _bot.emergency_stop()
    return jsonify(status), 200


@app.post('/api/v5/bot/tick')
def bot_tick():
    """Triggers automated bot cycle using trusted Windows-side MT5 quotes and fails closed on missing telemetry."""
    stress_obj = _v4_store.get_stress()
    stress_val = stress_obj['value'] if stress_obj else None
    try:
        res = _bot.tick(stress_val)
        return jsonify(res), 200
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503


@app.post('/api/v5/bot/backtest')
def bot_backtest():
    return jsonify({
        "status": "BLOCKED_RESEARCH_ACCOUNTING",
        "error": "Broker-specific research economics and historical cost configuration required. Use audited offline replay; no performance eligibility established."
    }), 503


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


def _read_only_account_error(account, expected_login, expected_server):
    if account is None:
        return {'error': 'Account state unavailable'}, 503
    if (type(getattr(account, 'login', None)) is not int or
            getattr(account, 'login', None) != expected_login or
            getattr(account, 'server', None) != expected_server):
        return {'error': 'Unexpected broker account identity'}, 403
    if (getattr(account, 'trade_allowed', None) is not False or
            getattr(account, 'trade_expert', None) is not False):
        return {'error': 'Gateway requires a read-only investor session'}, 403
    return None


@app.post('/analyze')
def analyze_psychology():
    try:
        body = request.get_json(silent=True)
    except RequestEntityTooLarge:
        return jsonify({'error': 'Request body too large'}), 413
    except (ValueError, RecursionError):
        return jsonify({'error': 'A valid JSON object is required'}), 400
    if not isinstance(body, dict):
        return jsonify({'error': 'A valid JSON object is required'}), 400
    if any(key in body for key in ('password', 'login', 'server')):
        return jsonify({'error': 'Broker credentials must never be submitted to this API'}), 400
    # Android sync sends {}. No client-supplied broker/account options are used;
    # this allowlist also rejects nested, aliased and differently cased secrets.
    if body:
        return jsonify({'error': 'This endpoint accepts only an empty JSON object'}), 400

    try:
        login = int(os.environ['MT5_LOGIN'])
        password = os.environ['MT5_INVESTOR_PASSWORD']
        server = os.environ['MT5_SERVER']
        if login <= 0 or not password or not server.strip():
            raise ValueError('MT5 credentials incomplete')
    except (KeyError, ValueError):
        return jsonify({'error': 'MT5 not configured on gateway host'}), 503

    try:
        import MetaTrader5 as mt5
    except Exception:
        app.logger.warning('MT5 read-only library unavailable')
        return jsonify({'error': 'MT5 library unavailable; Windows host required'}), 503

    with _mt5_lock:
        initialized = False
        payload, status = {'error': 'MT5 terminal connection failed'}, 503
        try:
            initialized = bool(mt5.initialize(login=login, password=password, server=server))
            if initialized:
                account_error = _read_only_account_error(mt5.account_info(), login, server)
                if account_error:
                    payload, status = account_error
                else:
                    now = datetime.now(timezone.utc)
                    deals = mt5.history_deals_get(now - timedelta(days=7), now)
                    if deals is None:
                        payload, status = {'error': 'MT5 history retrieval failed'}, 503
                    else:
                        # Fail closed if terminal identity or permissions changed
                        # while retrieving history; never expose the other account.
                        account_error = _read_only_account_error(mt5.account_info(), login, server)
                        if account_error:
                            payload, status = account_error
                        else:
                            payload, status = {**analyze_deals(deals), 'analysis_type': 'DEAL_HEURISTICS',
                                               'timebase_status': 'TIMEBASE_UNVERIFIED',
                                               'execution_policy': 'RESEARCH_ONLY_LOCKED'}, 200
        except Exception:
            # Broker/library exceptions can echo initialization credentials.
            # Never include exception text, traceback, account details or payload.
            app.logger.warning('MT5 read-only request failed')
            payload, status = {'error': 'MT5 operation failed'}, 503
        finally:
            if initialized:
                try:
                    mt5.shutdown()
                except Exception:
                    app.logger.warning('MT5 read-only cleanup failed')
                    payload, status = {'error': 'MT5 connection cleanup failed'}, 503
        return jsonify(payload), status


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
