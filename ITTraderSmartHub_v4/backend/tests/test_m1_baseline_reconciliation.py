"""M1 reconciliation regressions: lock in what is actually TRUE at 0c0624f.

These tests exist because the first WorkBuddy audit carried forward two obsolete
defects from a 2026-11-02 discovery report. Both were already fixed in the
baseline. Rather than "repairing" working code, these adversarial tests make
the corrected state explicit and prevent accidental regression.

All dependencies are mock/local. No broker, credentials, orders or network.
"""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_analyze_api import ADMIN, FakeMT5, api  # noqa: F401  (pytest fixture)

BACKEND = Path(__file__).resolve().parents[1]


# ── 1. /analyze NameError is OBSOLETE ────────────────────────────────────────

def test_analyze_route_has_valid_comprehension_at_baseline():
    source = (BACKEND / 'app.py').read_text(encoding='utf-8')
    assert "any(key in body for key in ('password', 'login', 'server'))" in source
    # The obsolete defect was a mismatched loop variable, e.g. `for k in (...)`.
    assert 'any(key in body for k in ' not in source


def test_analyze_authenticated_empty_body_does_not_raise_nameerror(api):
    """A valid request must reach the mocked MT5 layer, not crash on a typo.

    The fixture sets TESTING=True, so an unhandled NameError propagates here and
    fails the test with that exact exception rather than being masked as HTTP 500.
    """
    client, fake, module = api
    try:
        response = client.post('/analyze', json={}, headers=ADMIN)
    except NameError as exc:
        pytest.fail(f'obsolete /analyze NameError reappeared: {exc}')
    assert response.status_code == 200
    assert response.get_json()['analysis_type'] == 'DEAL_HEURISTICS'
    assert response.get_json()['timebase_status'] == 'TIMEBASE_UNVERIFIED'
    assert fake.calls  # route executed through to the mocked MT5 layer
    assert 'order_send' not in fake.calls


@pytest.mark.parametrize('secret_key', ['password', 'login', 'server'])
def test_analyze_rejects_credential_keys_without_500(api, secret_key):
    client, fake, _ = api
    response = client.post('/analyze', json={secret_key: 'x'}, headers=ADMIN)
    assert response.status_code == 400
    assert 'credentials' in response.get_json()['error'].lower()
    assert fake.calls == [], 'MT5 must not be touched for a rejected request'


def test_trade_analysis_module_contains_no_broken_body_expression():
    source = (BACKEND / 'trade_analysis.py').read_text(encoding='utf-8')
    assert 'any(key in body' not in source
    assert 'def analyze_deals' in source


# ── 2. BotController last_price AttributeError is OBSOLETE ───────────────────

def test_controller_source_has_no_legacy_attribute_references():
    source = (BACKEND / 'bot' / 'bot_controller.py').read_text(encoding='utf-8')
    assert 'last_price' not in source
    assert 'is_data_fresh' not in source
    assert 'order_send' not in source


def test_controller_paper_and_demo_modes_fail_closed():
    from bot import BotController, BotMode
    from bot.bot_controller import PaperSafetyError

    c = BotController()
    assert c.mode is BotMode.OFF
    with pytest.raises(PaperSafetyError, match='PAPER_BLOCKED'):
        c.set_mode('PAPER', admin_passcode='anything')
    with pytest.raises(PermissionError, match='RESEARCH_ONLY_EXECUTION_LOCK'):
        c.set_mode('DEMO', admin_passcode='anything')
    assert c.mode is BotMode.OFF
    assert c.demo_adapter.enabled is False
    assert c.get_status()['execution_policy'] == 'RESEARCH_ONLY_LOCKED'
    assert c.get_status()['paper_trading']['eligible'] is False


def test_controller_tick_cannot_run_a_trading_cycle_even_if_forced():
    """Injecting adapters or forcing the enum must not unlock P&L paths."""
    from bot import BotController, BotMode
    from bot.bot_controller import PaperSafetyError

    c = BotController()
    c.set_mode('BACKTEST')
    assert c.mode is BotMode.BACKTEST
    c.mode = BotMode.PAPER  # adversarial forced state
    with pytest.raises(PaperSafetyError, match='TRADING_CYCLE_BLOCKED'):
        c.tick()
    assert c.mode is BotMode.OFF
    assert c.demo_adapter.enabled is False


def test_demo_adapter_never_submits_even_when_flag_forced_true():
    from bot import DemoMT5ExecutionAdapter

    a = DemoMT5ExecutionAdapter()
    assert a.enable_demo_mode('admin') is False and a.enabled is False
    a.enabled = True  # adversarial mutation of the mutable flag
    with pytest.raises(PermissionError, match='prohibited'):
        a.execute_demo_order('x', 'USTECH100M', 'BUY', 1, 1, 1, 1)


def test_demo_execution_source_has_no_mt5_import_or_order_call():
    source = (BACKEND / 'bot' / 'demo_execution.py').read_text(encoding='utf-8')
    assert 'import MetaTrader5' not in source
    assert 'order_send' not in source


def test_no_python_order_send_call_site_in_backend_source():
    """AST-based detection: docstrings mentioning order_send() are NOT call sites.

    The first WorkBuddy audit claimed "zero order_send call sites" using a
    substring scan. `bot/paper_trading.py` contains the phrase
    "Zero calls to live MetaTrader5.order_send()" inside a docstring, so a naive
    scan produces a false positive. Parse the syntax tree instead.
    """
    import ast

    offenders = []
    for path in BACKEND.rglob('*.py'):
        parts = path.parts
        if ('tests' in parts or '__pycache__' in parts or 'site-packages' in parts
                or any(p.startswith('.venv') for p in parts)):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            called = fn.attr if isinstance(fn, ast.Attribute) else (
                fn.id if isinstance(fn, ast.Name) else None)
            if called == 'order_send':
                offenders.append(f'{path.relative_to(BACKEND)}:{node.lineno}')
    assert offenders == [], f'order_send call sites found: {offenders}'


# ── 3. Remote demo-trading branch must stay excluded ─────────────────────────

EXCLUDED_BRANCH_TIP = '093956d9c22e9d0f80ad0193f119b9783d394667'
EXCLUDED_ADAPTER_BLOB = '10febf27378b26a40028135959d2722e7edf84ab'
EXECUTION_LOCK_COMMIT = 'ae707c0'


def _git(*args):
    return subprocess.run(['git', *args], cwd=BACKEND.parent,
                          capture_output=True, text=True, timeout=15)


def test_excluded_demo_trading_adapter_blob_is_not_in_current_tree():
    """The dangerous branch exists remotely and is a HISTORICAL ancestor.

    It is NOT an active base for M1 work: commit ae707c0 removed the submitting
    adapter. Verify the current tree's blob differs from the excluded branch's
    unsafe blob, and that the current adapter contains no submission call.
    """
    try:
        head_blob = _git('rev-parse', 'HEAD:./backend/bot/demo_execution.py')
        old_blob = _git('rev-parse', f'{EXCLUDED_BRANCH_TIP}:./backend/bot/demo_execution.py')
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip('git unavailable in this environment')
    if head_blob.returncode or old_blob.returncode:
        pytest.skip('excluded branch object not available locally')
    assert old_blob.stdout.strip() == EXCLUDED_ADAPTER_BLOB
    assert head_blob.stdout.strip() != EXCLUDED_ADAPTER_BLOB

    current = _git('show', 'HEAD:./backend/bot/demo_execution.py')
    assert 'order_send' not in current.stdout
    assert 'import MetaTrader5' not in current.stdout


def test_excluded_branch_tip_was_superseded_by_execution_lock_commit():
    """Document the real ancestry: the unsafe code was removed, not inherited."""
    try:
        result = _git('merge-base', '--is-ancestor', EXCLUDED_BRANCH_TIP, EXECUTION_LOCK_COMMIT)
        lock = _git('show', '-s', '--format=%H', EXECUTION_LOCK_COMMIT)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip('git unavailable in this environment')
    if result.returncode >= 128:
        pytest.skip('excluded branch object not available locally')
    # The lock commit descends from the excluded tip; that is HOW it removed the
    # unsafe adapter. M1 work must not merge FROM the excluded tip going forward.
    assert result.returncode == 0
    assert lock.stdout.strip()
    working = (BACKEND / 'bot' / 'demo_execution.py').read_text(encoding='utf-8')
    assert 'RESEARCH_ONLY_EXECUTION_LOCK' in working
    assert 'order_send' not in working
