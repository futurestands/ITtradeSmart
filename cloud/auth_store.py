"""Transactional durable cloud device store. No in-memory or SQLite fallback.

Schema installation is an explicit operator task against an approved target.
Only token/code hashes enter storage. Connection details never enter responses.
"""
from contextlib import contextmanager
from hashlib import sha256
import os
import secrets
import time
from urllib.parse import parse_qs, urlsplit


def digest(value):
    return sha256(value.encode('utf-8')).hexdigest()


def new_token(kind):
    return 'shc_' + kind + '_' + secrets.token_urlsafe(32)


@contextmanager
def postgres_connection():
    dsn = os.environ.get('SMARTHUB_CLOUD_DATABASE_URL', '')
    parsed = urlsplit(dsn)
    if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname:
        raise RuntimeError('Cloud authentication is not configured')
    if parse_qs(parsed.query).get('sslmode') != ['verify-full']:
        raise RuntimeError('Verified database TLS is required')
    import psycopg
    with psycopg.connect(dsn, connect_timeout=5, options='-c statement_timeout=5000') as connection:
        yield connection


class Store:
    def __init__(self, connect=postgres_connection, clock=time.time):
        self.connect, self.clock = connect, clock

    def audit(self, event, principal='anonymous'):
        with self.connect() as db:
            db.execute('INSERT INTO smarthub_cloud_auth.audit(occurred_at,event,principal_hash) VALUES (%s,%s,%s)',
                       (int(self.clock()), event, digest(principal)))

    def rate(self, scope, identity, limit):
        # Atomic durable bucket, shared across cold starts/processes/instances.
        bucket = f'{scope}:{int(self.clock())//60}:{digest(identity)}'
        with self.connect() as db:
            row = db.execute('INSERT INTO smarthub_cloud_auth.rate_limits(bucket,count) VALUES (%s,1) '
                             'ON CONFLICT(bucket) DO UPDATE SET count=smarthub_cloud_auth.rate_limits.count+1 '
                             'RETURNING count', (bucket,)).fetchone()
            return row[0] <= limit

    def principal(self, token):
        if not isinstance(token, str) or not token.startswith('shc_access_') or len(token) > 100:
            return None
        with self.connect() as db:
            return db.execute('SELECT d.id,d.role FROM smarthub_cloud_auth.devices d '
                              'JOIN smarthub_cloud_auth.sessions s ON s.device_id=d.id '
                              'WHERE s.access_hash=%s AND s.access_until>%s AND d.revoked=FALSE',
                              (digest(token), int(self.clock()))).fetchone()

    def _session(self, db, device_id):
        access, refresh = new_token('access'), new_token('refresh')
        now = int(self.clock())
        db.execute('INSERT INTO smarthub_cloud_auth.sessions VALUES (%s,%s,%s,%s,%s)',
                   (digest(access), digest(refresh), device_id, now+3600, now+2592000))
        return dict(device_token=access, refresh_token=refresh, expires_at=now+3600,
                    refresh_expires_at=now+2592000, device_id=device_id)

    def enrollment_code(self):
        code = new_token('enroll')
        with self.connect() as db:
            db.execute('INSERT INTO smarthub_cloud_auth.enrollment VALUES (%s,%s,FALSE)',
                       (digest(code), int(self.clock())+600))
        return code

    def enroll(self, device_id, name, code):
        with self.connect() as db:
            consumed = db.execute('UPDATE smarthub_cloud_auth.enrollment SET used=TRUE '
                                  'WHERE code_hash=%s AND used=FALSE AND expires_at>%s RETURNING code_hash',
                                  (digest(code), int(self.clock()))).fetchone()
            if consumed is None:
                return None
            # Client identifiers must not select or overwrite an existing principal.
            # A replacement enrollment is a new independently revocable principal.
            device_id = 'cloud-' + secrets.token_hex(16)
            db.execute('INSERT INTO smarthub_cloud_auth.devices VALUES (%s,%s,%s,FALSE,%s)',
                       (device_id, name, 'device', int(self.clock())))
            return self._session(db, device_id)

    def renew(self, refresh):
        if not isinstance(refresh, str) or not refresh.startswith('shc_refresh_') or len(refresh) > 100:
            return None
        with self.connect() as db:
            # Consume old session atomically. Rollback restores it on issuance failure.
            row = db.execute('DELETE FROM smarthub_cloud_auth.sessions WHERE refresh_hash=%s '
                             'AND refresh_until>%s AND EXISTS (SELECT 1 FROM smarthub_cloud_auth.devices d '
                             'WHERE d.id=device_id AND d.revoked=FALSE) RETURNING device_id',
                             (digest(refresh), int(self.clock()))).fetchone()
            return self._session(db, row[0]) if row else None

    def revoke(self, device_id):
        with self.connect() as db:
            return db.execute('UPDATE smarthub_cloud_auth.devices SET revoked=TRUE WHERE id=%s RETURNING id',
                              (device_id,)).fetchone() is not None
