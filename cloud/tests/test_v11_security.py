"""v1.1 security contracts: offline SQL parsing, never a database connection."""
import json
from pathlib import Path

from pglast import parse_sql
import pytest
from auth_store import IDENTITY_SQL, DB_NOW

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = 'smarthub_cloud_runtime'
OPERATOR = 'smarthub_cloud_operator'


def statements():
    return [item.stmt() for item in parse_sql((ROOT/'schema.sql').read_text())]


def test_catalog_identity_guard_and_database_clock_parse_as_postgresql():
    assert parse_sql(IDENTITY_SQL) and parse_sql(DB_NOW)


def test_final_gate_membership_options_are_explicit():
    membership = [s for s in statements() if s['@'] == 'GrantRoleStmt']
    options = {o['defname']:o['arg']['boolval'] for s in membership for o in (s['opt'] or ())}
    assert options == {'admin':False, 'inherit':False, 'set':True}


def test_final_gate_has_no_definer_routine_and_refuses_wrong_database_before_ddl():
    from pglast import parse_plpgsql
    sql = (ROOT/'schema.sql').read_text()
    statements = [item.stmt() for item in parse_sql(sql)]
    assert not any(item['@'] in ('CreateFunctionStmt','AlterOwnerStmt') for item in statements)
    assert 'SECURITY DEFINER' not in sql
    assert "pg_catalog.current_database() <> 'smarthub-phase3-preview'" in sql
    assert sql.index('DO $target_gate$') < sql.index('CREATE SCHEMA')
    block = sql[sql.index('DO $target_gate$'):sql.index('CREATE SCHEMA')]
    assert parse_plpgsql(block)
    assert statements[0]['@'] == statements[-1]['@'] == 'TransactionStmt'


def granted(table, role, operation):
    columns = set()
    for item in statements():
        if item['@'] != 'GrantStmt' or not item['is_grant']:
            continue
        if not any(x.get('relname') == table for x in item.get('objects') or ()):
            continue
        if not any(x.get('rolename') == role for x in item.get('grantees') or ()):
            continue
        for privilege in item.get('privileges') or ():
            if privilege['priv_name'] == operation:
                columns |= {x['sval'] for x in privilege['cols']} if privilege['cols'] else {'*'}
        assert not item['grant_option']
    return columns


@pytest.mark.parametrize('operation,forbidden', [('insert', 'role'), ('insert', 'revoked'),
                                                ('insert', 'created_at'), ('update', 'role'),
                                                ('update', 'id'), ('update', 'created_at')])
def test_runtime_has_no_role_or_identity_write_grant(operation, forbidden):
    rights = granted('devices', RUNTIME, operation)
    assert '*' not in rights and forbidden not in rights


def test_no_public_all_table_or_all_privilege_grant_bypasses_column_controls():
    for item in statements():
        if item['@'] != 'GrantStmt' or not item['is_grant']:
            continue
        assert not any(r.get('rolename') is None for r in item['grantees'])
        if any(r.get('rolename') == RUNTIME for r in item['grantees']):
            assert item['privileges'] is not None
            assert item['targtype']['name'] == 'ACL_TARGET_OBJECT'


def test_enrollment_uses_database_device_default():
    table = next(s for s in statements() if s['@'] == 'CreateStmt' and s['relation']['relname'] == 'devices')
    role = next(c for c in table['tableElts'] if c.get('colname') == 'role')
    assert any(c.get('raw_expr', {}).get('val', {}).get('sval') == 'device'
               for c in role['constraints'] if c.get('raw_expr'))
    assert granted('devices', RUNTIME, 'insert') == {'id', 'name'}
    assert granted('devices', RUNTIME, 'update') == {'revoked'}


@pytest.mark.parametrize('operation', ['select', 'update', 'delete', 'truncate'])
def test_web_runtime_cannot_read_or_rewrite_audit(operation):
    assert granted('audit', RUNTIME, operation) == set()


def test_offline_operator_can_read_audit_but_not_erase_it():
    assert granted('audit', OPERATOR, 'select')
    assert granted('audit', OPERATOR, 'insert') == {'occurred_at', 'event', 'principal_hash'}
    assert not granted('audit', OPERATOR, 'update')
    assert not granted('audit', OPERATOR, 'delete')


def test_final_gate_runtime_cannot_overwrite_audit_identity_or_reset_its_sequence():
    assert granted('audit', RUNTIME, 'insert') == {'occurred_at','event','principal_hash'}
    assert not granted('audit_id_seq', RUNTIME, 'update')
    assert granted('audit_id_seq', RUNTIME, 'usage')


def test_runtime_cannot_delete_rate_buckets_or_extend_their_lifetime():
    assert not granted('rate_limits', RUNTIME, 'delete')
    assert granted('rate_limits', RUNTIME, 'update') == {'count'}
    assert granted('rate_limits', OPERATOR, 'delete')


def test_admin_sessions_have_row_policy_write_protection():
    policies = [s for s in statements() if s['@'] == 'CreatePolicyStmt'
                and s['table']['relname'] == 'sessions' and s['cmd_name'] in ('insert', 'delete')
                and any(r['rolename'] == RUNTIME for r in s['roles'])]
    assert {p['cmd_name'] for p in policies} == {'insert', 'delete'}
    for policy in policies:
        content = json.dumps(policy)
        assert 'device' in content and 'role' in content and 'device_id' in content
    # ENABLE/FORCE are essential: policies alone do not activate row security.
    sql = (ROOT/'schema.sql').read_text()
    for table in ('devices', 'sessions'):
        assert f'ALTER TABLE smarthub_cloud_auth.{table} ENABLE ROW LEVEL SECURITY;' in sql
        assert f'ALTER TABLE smarthub_cloud_auth.{table} FORCE ROW LEVEL SECURITY;' in sql


def test_login_mapping_never_grants_operator_to_the_web_login():
    roles = [s for s in statements() if s['@'] == 'CreateRoleStmt']
    for name in (RUNTIME, OPERATOR, 'smarthub_cloud_preview_login'):
        role = next(r for r in roles if r['role'] == name)
        options = {o['defname']: o.get('arg') for o in role['options']}
        assert options['canlogin']['boolval'] is False
        assert options['inherit']['boolval'] is False
    membership = [s for s in statements() if s['@'] == 'GrantRoleStmt']
    assert len(membership) == 3
    for grant in membership:
        assert grant['granted_roles'][0]['priv_name'] == RUNTIME
        assert grant['grantee_roles'][0]['rolename'] == 'smarthub_cloud_preview_login'


def evaluate(node, row, devices):
    """Small independent interpreter for the row-policy expressions, not a DB.

    Uses actual parsed SQL expressions so OR TRUE or an extra permissive policy
    would fail the negative cases below. Real PostgreSQL execution is still pending.
    """
    kind = node['@']
    if kind == 'A_Const':
        value = node['val']
        return value.get('sval', value.get('boolval', value.get('ival')))
    if kind == 'ColumnRef':
        return row['.'.join(item['sval'] for item in node['fields'])]
    if kind == 'A_Expr':
        assert [item['sval'] for item in node['name']] == ['=']
        return evaluate(node['lexpr'], row, devices) == evaluate(node['rexpr'], row, devices)
    if kind == 'BoolExpr':
        values = [evaluate(item, row, devices) for item in node['args']]
        return all(values) if node['boolop']['name'] == 'AND_EXPR' else any(values)
    if kind == 'SubLink':
        assert node['subLinkType']['name'] == 'EXISTS_SUBLINK'
        query = node['subselect']
        assert query['fromClause'][0]['relname'] == 'devices'
        return any(evaluate(query['whereClause'], row | {'d.'+k:v for k,v in device.items()}, devices)
                   for device in devices)
    raise AssertionError('Unreviewed row-policy expression: '+kind)


def admitted(table, command, row, devices):
    policies = [s for s in statements() if s['@'] == 'CreatePolicyStmt'
                and s['table']['relname'] == table and s['cmd_name'] in (command, 'all')
                and any(r['rolename'] in (RUNTIME, None) for r in s['roles'])]
    # All current runtime policies are permissive; evaluate their actual OR union.
    assert all(p['permissive'] for p in policies)
    expressions = [p['with_check'] if command == 'insert' else p['qual'] for p in policies]
    if command == 'update':
        return any(evaluate(p['qual'], row, devices) and evaluate(p['with_check'], row, devices) for p in policies)
    return any(evaluate(expression, row, devices) for expression in expressions)


@pytest.mark.parametrize('role,revoked,allowed', [('device',False,True), ('device',True,False),
                                               ('admin',False,False), ('admin',True,False)])
def test_insert_device_policy_does_not_admit_administrators(role, revoked, allowed):
    assert admitted('devices', 'insert', {'role':role, 'revoked':revoked}, []) is allowed


@pytest.mark.parametrize('role,revoked,allowed', [('device',True,True), ('device',False,False),
                                               ('admin',True,False), ('admin',False,False)])
def test_revoke_policy_cannot_promote_or_unrevoke(role, revoked, allowed):
    assert admitted('devices', 'update', {'role':role, 'revoked':revoked}, []) is allowed


@pytest.mark.parametrize('role,revoked,allowed', [('device',False,True), ('device',True,False),
                                               ('admin',False,False), ('admin',True,False)])
def test_session_insert_policy_cannot_impersonate_admin(role, revoked, allowed):
    device = {'id':'principal1','role':role,'revoked':revoked}
    assert admitted('sessions', 'insert', {'device_id':'principal1'}, [device]) is allowed


@pytest.mark.parametrize('role,allowed', [('device',True), ('admin',False)])
def test_session_delete_policy_preserves_operator_sessions(role, allowed):
    assert admitted('sessions', 'delete', {'device_id':'principal1'}, [{'id':'principal1','role':role}]) is allowed


def test_cleanup_is_bounded_and_only_expired_rows_are_eligible():
    text = (ROOT/'maintenance/purge_expired_rate_limits.sql').read_text()
    parsed = parse_sql(text)
    assert parsed
    assert 'LIMIT 1000' in text
    assert 'expires_at <= ' in text
    assert 'statement_timestamp()' in text
    assert text.count('::bigint - 300') == 2
    assert 'RETURNING 1' in text
    assert 'EXPIRED_RATE_BUCKETS_PURGED' in text
    assert 'DELETE FROM smarthub_cloud_auth.audit' not in text
    assert 'UPDATE smarthub_cloud_auth.audit' not in text
