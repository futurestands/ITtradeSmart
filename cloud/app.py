"""Authenticated stateless cloud boundary. Never imports MT5 or trains models."""
from datetime import datetime, timezone
import re
from flask import Flask, jsonify, request, g
from werkzeug.exceptions import HTTPException
from auth_store import Store
from research_contract import unavailable as unavailable_research


def create_app(store=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16384
    app.extensions['device_store'] = store or Store()

    def backend():
        return app.extensions['device_store']

    def error(code, status):
        return jsonify(error=code, action='NO_TRADE', model_status='MODEL_NOT_READY'), status

    def body(fields):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != set(fields):
            return None
        if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in data.values()):
            return None
        return data

    @app.before_request
    def authorize():
        if request.path in ('/', '/health'):
            return None
        if request.path in ('/api/v5/device/enroll', '/api/v5/device/renew'):
            if not backend().rate('enrollment', request.remote_addr or 'unknown', 10):
                backend().audit('ENROLLMENT_RATE_LIMIT')
                return error('RATE_LIMITED', 429)
            return None
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer shc_access_') or len(auth) > 120:
            return error('CLOUD_DEVICE_AUTH_REQUIRED', 401)
        token = auth[7:]
        if not backend().rate('access', token, 120):
            backend().audit('ACCESS_RATE_LIMIT', token)
            return error('RATE_LIMITED', 429)
        principal = backend().principal(token)
        if principal is None:
            backend().audit('AUTH_REJECTED', token)
            return error('TOKEN_EXPIRED_REVOKED_OR_INVALID', 401)
        g.device_id, g.role = principal
        if request.path.startswith('/api/v5/admin/') and g.role != 'admin':
            backend().audit('ROLE_DENIED', g.device_id)
            return error('ADMIN_ROLE_REQUIRED', 403)
        backend().audit('AUTH_ACCEPTED', g.device_id)

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY', 'Strict-Transport-Security': 'max-age=31536000',
            'X-Smarthub-Generated-At': datetime.now(timezone.utc).isoformat()})
        return response

    @app.errorhandler(Exception)
    def safe_failure(exc):
        if isinstance(exc, HTTPException):
            return error('HTTP_'+str(exc.code), exc.code)
        return error('CLOUD_AUTH_UNAVAILABLE', 503)  # Never echo/log driver exceptions.

    @app.get('/')
    @app.get('/health')
    def health():
        return jsonify(status='ok', service='ittrader-smarthub-cloud-api', model_ready=False,
                       market_data_connected=False, execution_policy='RESEARCH_ONLY_LOCKED')

    @app.post('/api/v5/device/enroll')
    def enroll():
        data = body(('device_id', 'device_name', 'pairing_code'))
        if (data is None or not re.fullmatch(r'[A-Za-z0-9_-]{3,64}', data['device_id'])
                or not data['pairing_code'].startswith('shc_enroll_')):
            return error('INVALID_ENROLLMENT', 400)
        result = backend().enroll(data['device_id'], data['device_name'], data['pairing_code'])
        backend().audit('DEVICE_ENROLLED' if result else 'ENROLLMENT_REJECTED', data['device_id'])
        return (jsonify(result), 201) if result else error('ENROLLMENT_CODE_INVALID_OR_USED', 401)

    @app.post('/api/v5/device/renew')
    def renew():
        data = body(('refresh_token',))
        if data is None:
            return error('INVALID_RENEWAL', 400)
        result = backend().renew(data['refresh_token'])
        backend().audit('SESSION_RENEWED' if result else 'RENEWAL_REJECTED')
        return jsonify(result) if result else error('REFRESH_EXPIRED_REVOKED_OR_USED', 401)

    @app.post('/api/v5/device/revoke')
    def revoke():
        if request.get_data():
            return error('NO_INPUTS_ACCEPTED', 400)
        backend().revoke(g.device_id)
        backend().audit('DEVICE_SELF_REVOKED', g.device_id)
        return jsonify(status='REVOKED')

    @app.post('/api/v5/admin/enrollment-codes')
    def code():
        if request.get_data():
            return error('NO_INPUTS_ACCEPTED', 400)
        value = backend().enrollment_code()
        backend().audit('ENROLLMENT_CODE_ISSUED', g.device_id)
        return jsonify(pairing_code=value, expires_in_seconds=600), 201

    @app.post('/api/v5/admin/devices/<device_id>/revoke')
    def admin_revoke(device_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{3,64}', device_id):
            return error('INVALID_DEVICE_ID', 400)
        backend().revoke(device_id)
        backend().audit('ADMIN_DEVICE_REVOKED', device_id)
        return jsonify(status='REVOKED')

    @app.get('/api/v5/ai/status')
    def ai_status():
        return jsonify(schema_version='1.0', connection_status='UNAVAILABLE',
            model_status='MODEL_NOT_READY', model_trained=False, model=None, probability=None,
            advisory_only=True, reason_code='SERVICE_NOT_CONFIGURED',
            explanation='Authenticated cloud API available; no eligible cloud model or Lab is connected.',
            execution_policy='RESEARCH_ONLY_LOCKED', timebase_status='TIMEBASE_UNVERIFIED')

    @app.get('/api/v5/ai/research-progress')
    def research():
        return jsonify(unavailable_research())  # Reuse existing tested contract, no file load.

    @app.route('/api/v5/ai/advisory', methods=['GET', 'POST'])
    def advisory():
        return jsonify(schema_version='1.0', action='NO_TRADE', status='BLOCKED',
            reason_code='NO_VALIDATED_CLOUD_MODEL', model_status='MODEL_NOT_READY',
            probability=None, model_confidence=None, research_eligible=False,
            execution_policy='RESEARCH_ONLY_LOCKED', source='CLOUD_METADATA_ONLY')

    return app


app = create_app()
