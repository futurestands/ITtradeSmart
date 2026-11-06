"""Transactional durable cloud device store. No in-memory or SQLite fallback.

Schema installation is an explicit operator task against an approved target.
Only token/code hashes enter storage. Connection details never enter responses.
"""
from contextlib import contextmanager
from hashlib import sha256
import os
import secrets
import certifi
from urllib.parse import parse_qs, unquote, urlsplit

PRIVATE_LOGIN = 'smarthub_cloud_preview_login'
RUNTIME_ROLE = 'smarthub_cloud_runtime'
DB_NOW = 'SELECT floor(extract(epoch FROM statement_timestamp()))::bigint'
IDENTITY_SQL = (
    "SELECT session_user,current_user,rolsuper,rolcreaterole,rolcreatedb,rolbypassrls,"
    "rolreplication,rolinherit,pg_has_role(session_user,'smarthub_cloud_operator','MEMBER'),"
    "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname NOT IN "
    "('smarthub_cloud_preview_login','smarthub_cloud_runtime') "
    "AND pg_has_role(session_user,r.oid,'MEMBER')),"
    "EXISTS (SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname='smarthub_cloud_runtime' "
    "AND (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolbypassrls "
    "OR r.rolreplication OR r.rolcanlogin OR r.rolinherit)),"
    "(EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles r "
    "ON n.nspowner=r.oid WHERE n.nspname='smarthub_cloud_auth' "
    "AND r.rolname IN ('smarthub_cloud_preview_login','smarthub_cloud_runtime')) "
    "OR EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n "
    "ON c.relnamespace=n.oid JOIN pg_catalog.pg_roles r ON c.relowner=r.oid "
    "WHERE n.nspname='smarthub_cloud_auth' "
    "AND r.rolname IN ('smarthub_cloud_preview_login','smarthub_cloud_runtime'))),"
    "((SELECT count(*) FROM pg_catalog.pg_auth_members m "
    "JOIN pg_catalog.pg_roles u ON m.member=u.oid "
    "JOIN pg_catalog.pg_roles r ON m.roleid=r.oid "
    "WHERE u.rolname='smarthub_cloud_preview_login' AND r.rolname='smarthub_cloud_runtime' "
    "AND NOT m.admin_option AND NOT m.inherit_option AND m.set_option)<>1) "
    "FROM pg_catalog.pg_roles WHERE rolname=session_user"
)
RATE_LIMITS = {'enrollment': 10, 'access': 120}


def digest(value):
    return sha256(value.encode('utf-8')).hexdigest()


def new_token(kind):
    return 'shc_' + kind + '_' + secrets.token_urlsafe(32)


@contextmanager
def postgres_connection():
    environment = os.environ.get('VERCEL_ENV') or os.environ.get('SMARTHUB_CLOUD_ENVIRONMENT')
    if environment not in ('preview', 'development'):
        raise RuntimeError('Cloud authentication is restricted to Preview/Development')
    dsn = os.environ.get('SMARTHUB_CLOUD_DATABASE_URL', '')
    parsed = urlsplit(dsn)
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname:
        raise RuntimeError('Cloud authentication is not configured')
    params = parse_qs(parsed.query, keep_blank_values=True)
    if params.get('sslmode') != ['verify-full']:
        raise RuntimeError('Verified database TLS is required')
    if set(params)-{'sslmode', 'channel_binding'} or params.get('channel_binding', ['require']) != ['require']:
        raise RuntimeError('Unapproved database connection options')
    if unquote(parsed.username or '') != PRIVATE_LOGIN:
        raise RuntimeError('Dedicated private runtime login required')
    if os.environ.get('PGOPTIONS') or os.environ.get('PGSERVICE'):
        raise RuntimeError('Implicit PostgreSQL session configuration is not permitted')
    expected_host = os.environ.get('SMARTHUB_CLOUD_DATABASE_HOST', '')
    expected_database = os.environ.get('SMARTHUB_CLOUD_DATABASE_NAME', '')
    if (not expected_host or not expected_database or parsed.hostname != expected_host
            or not expected_host.endswith('.neon.tech') or '-pooler.' not in expected_host
            or unquote(parsed.path) != '/'+expected_database or parsed.port not in (None, 5432)):
        raise RuntimeError('Approved Neon pooled endpoint and database must match')
    import psycopg
    with psycopg.connect(dsn, connect_timeout=5,
                         sslmode='verify-full', sslrootcert=certifi.where(), channel_binding='require',
                         ssl_min_protocol_version='TLSv1.2', gssencmode='disable',
                         options='', autocommit=False, prepare_threshold=None) as connection:
        # Neon transaction pooling: no dependence on session/startup settings.
        connection.execute('SET LOCAL search_path = pg_catalog')
        connection.execute("SET LOCAL statement_timeout = '5s'")
        connection.execute("SET LOCAL idle_in_transaction_session_timeout = '10s'")
        identity = connection.execute(IDENTITY_SQL).fetchone()
        if identity != (PRIVATE_LOGIN, PRIVATE_LOGIN) + (False,)*11:
            raise RuntimeError('Database identity or privileges rejected')
        connection.execute('SET LOCAL ROLE smarthub_cloud_runtime')
        if connection.execute('SELECT current_user').fetchone() != (RUNTIME_ROLE,):
            raise RuntimeError('Runtime role mapping rejected')
        yield connection


class Store:
    def __init__(self, connect=postgres_connection):
        self.connect = connect

    @staticmethod
    def _now(db):
        return db.execute(DB_NOW).fetchone()[0]

    def audit(self, event, principal='anonymous'):
        with self.connect() as db:
            db.execute('INSERT INTO smarthub_cloud_auth.audit(occurred_at,event,principal_hash) VALUES (%s,%s,%s)',
                       (self._now(db), event, digest(principal)))

    def rate(self, scope, identity, limit):
        if scope not in RATE_LIMITS or type(limit) is not int or limit != RATE_LIMITS[scope]:
            raise ValueError('Unregistered rate-limit policy')
        # Explicit database-clock fixed windows; never delete/reset a live bucket.
        with self.connect() as db:
            start = self._now(db)//60*60
            row = db.execute('INSERT INTO smarthub_cloud_auth.rate_limits '
                             '(scope,identity_hash,window_start,expires_at,count) VALUES (%s,%s,%s,%s,1) '
                             'ON CONFLICT(scope,identity_hash,window_start) DO UPDATE SET count=CASE '
                             'WHEN smarthub_cloud_auth.rate_limits.count<%s '
                             'THEN smarthub_cloud_auth.rate_limits.count+1 '
                             'ELSE smarthub_cloud_auth.rate_limits.count END RETURNING count',
                             (scope, digest(identity), start, start+60, limit+1)).fetchone()
            return row[0] <= limit

    def principal(self, token):
        if not isinstance(token, str) or not token.startswith('shc_access_') or len(token) > 100:
            return None
        with self.connect() as db:
            return db.execute('SELECT d.id,d.role FROM smarthub_cloud_auth.devices d '
                              'JOIN smarthub_cloud_auth.sessions s ON s.device_id=d.id '
                              'WHERE s.access_hash=%s AND s.access_until>%s AND d.revoked=FALSE',
                              (digest(token), self._now(db))).fetchone()

    def _session(self, db, device_id):
        row = db.execute('SELECT role FROM smarthub_cloud_auth.devices WHERE id=%s AND revoked=FALSE',
                         (device_id,)).fetchone()
        if row != ('device',):
            raise PermissionError('Administrator sessions require private operator bootstrap')
        access, refresh = new_token('access'), new_token('refresh')
        now = self._now(db)
        db.execute('INSERT INTO smarthub_cloud_auth.sessions '
                   '(access_hash,refresh_hash,device_id,access_until,refresh_until) VALUES (%s,%s,%s,%s,%s)',
                   (digest(access), digest(refresh), device_id, now+3600, now+2592000))
        return dict(device_token=access, refresh_token=refresh, expires_at=now+3600,
                    refresh_expires_at=now+2592000, device_id=device_id)

    def enrollment_code(self):
        code = new_token('enroll')
        with self.connect() as db:
            db.execute('INSERT INTO smarthub_cloud_auth.enrollment VALUES (%s,%s,FALSE)',
                       (digest(code), self._now(db)+600))
        return code

    def enroll(self, device_id, name, code):
        with self.connect() as db:
            consumed = db.execute('UPDATE smarthub_cloud_auth.enrollment SET used=TRUE '
                                  'WHERE code_hash=%s AND used=FALSE AND expires_at>%s RETURNING code_hash',
                                  (digest(code), self._now(db))).fetchone()
            if consumed is None:
                return None
            # Client identifiers must not select or overwrite an existing principal.
            # A replacement enrollment is a new independently revocable principal.
            device_id = 'cloud-' + secrets.token_hex(16)
            db.execute('INSERT INTO smarthub_cloud_auth.devices (id,name) VALUES (%s,%s)',
                       (device_id, name))
            return self._session(db, device_id)

    def renew(self, refresh):
        if not isinstance(refresh, str) or not refresh.startswith('shc_refresh_') or len(refresh) > 100:
            return None
        with self.connect() as db:
            # Consume old session atomically. Rollback restores it on issuance failure.
            row = db.execute('DELETE FROM smarthub_cloud_auth.sessions WHERE refresh_hash=%s '
                             'AND refresh_until>%s AND EXISTS (SELECT 1 FROM smarthub_cloud_auth.devices d '
                             "WHERE d.id=device_id AND d.revoked=FALSE AND d.role='device') RETURNING device_id",
                             (digest(refresh), self._now(db))).fetchone()
            return self._session(db, row[0]) if row else None

    def revoke(self, device_id):
        with self.connect() as db:
            return db.execute("UPDATE smarthub_cloud_auth.devices SET revoked=TRUE WHERE id=%s AND role='device' RETURNING id",
                              (device_id,)).fetchone() is not None
