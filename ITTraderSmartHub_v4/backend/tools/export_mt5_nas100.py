"""Export CLOSED MT5 OHLCV bars for research; never sends trade orders.

Run from Windows with the already configured MT5 investor terminal session:
    python tools/export_mt5_nas100.py --symbol USTECH100M --timeframe M5 --count 10000 --out-dir data/nas100

Data are written to files under --out-dir and should be checked for provider
licensing and privacy before sharing. No account number, tokens or passwords are
written. The existing demo session must satisfy every disabled-trading gate;
the exporter never changes accounts or terminal permissions.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from math import isfinite
import os
from pathlib import Path
import subprocess

# Direct-script execution sets sys.path to tools/, not backend/.
# Add the project backend root without installing any new package.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nas100.candles import candles_from_rates, validate_candles

TIMEFRAMES = {'M1': (1, 'TIMEFRAME_M1'), 'M5': (5, 'TIMEFRAME_M5'),
              'M15': (15, 'TIMEFRAME_M15'), 'H1': (60, 'TIMEFRAME_H1')}


class ExportSafetyError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def validate_session(mt5, expected=None):
    """Check permission and demo identity gates without emitting identity values."""
    a, t = mt5.account_info(), mt5.terminal_info()
    message = 'Read-only connected demo MT5 session required; export aborted'
    if a is None or t is None or getattr(t, 'connected', None) is not True:
        raise ExportSafetyError('TERMINAL_NOT_CONNECTED', message)
    if type(getattr(a, 'trade_mode', None)) is not int or a.trade_mode != getattr(mt5, 'ACCOUNT_TRADE_MODE_DEMO', 0):
        raise ExportSafetyError('DEMO_ACCOUNT_REQUIRED', message)
    if (getattr(a, 'trade_allowed', None) is not False or getattr(a, 'trade_expert', None) is not False
            or getattr(t, 'trade_allowed', None) is not False):
        raise ExportSafetyError('TRADING_MUST_BE_DISABLED', message)
    identity = (getattr(a, 'login', None), getattr(a, 'server', None))
    if type(identity[0]) is not int or identity[0] <= 0 or not isinstance(identity[1], str) or not identity[1]:
        raise ExportSafetyError('SESSION_IDENTITY_UNAVAILABLE', 'Session identity unavailable; export aborted')
    if expected is not None and identity != expected:
        raise ExportSafetyError('SESSION_CHANGED', 'Session changed during export; export aborted')
    return identity


def export_closed_rates(mt5, *, symbol: str, timeframe: str, count: int, out_dir: Path,
                        collected_at: datetime):
    if timeframe not in TIMEFRAMES:
        raise ValueError('Unsupported timeframe')
    if type(count) is not int or count < 2 or count > 200000:
        raise ValueError('count must be between 2 and 200000')
    if not isinstance(symbol, str) or not 1 <= len(symbol) <= 32 or not all(
            ch.isalnum() or ch in '._-' for ch in symbol):
        raise ValueError('Invalid symbol')
    if not isinstance(collected_at, datetime) or collected_at.utcoffset() is None:
        raise ValueError('collected_at must be timezone-aware')
    collected_utc = collected_at.astimezone(timezone.utc)
    identity = validate_session(mt5)
    info = mt5.symbol_info(symbol)
    if info is None or getattr(info, 'name', None) != symbol:
        raise RuntimeError('Symbol not found on this broker; export aborted')
    for name in ('point', 'trade_tick_size', 'trade_contract_size', 'volume_min', 'volume_max', 'volume_step'):
        value = getattr(info, name, None)
        if type(value) not in (int, float) or not isfinite(value) or value <= 0:
            raise RuntimeError('Invalid symbol specification; export aborted')
    if info.volume_min > info.volume_max or info.volume_step > info.volume_max:
        raise RuntimeError('Invalid volume constraints; export aborted')
    mins, attr = TIMEFRAMES[timeframe]
    # Position zero is the current potentially unfinished candle; never request it.
    validate_session(mt5, identity)
    raw = mt5.copy_rates_from_pos(symbol, getattr(mt5, attr), 1, count)
    validate_session(mt5, identity)
    if raw is None or len(raw) == 0:
        raise RuntimeError('No historical rates returned; verify history availability')
    bars = candles_from_rates(raw)
    quality = validate_candles(bars, mins)
    if any(b.time > collected_utc for b in bars):
        raise ExportSafetyError('FUTURE_BAR_OPEN', 'Future bar opens against collection clock; export aborted')
    returned_count = len(bars)
    # Defend against the current bar accidentally being present despite start_pos=1.
    bars = [b for b in bars if b.time + timedelta(minutes=mins) <= collected_utc]
    if not bars:
        raise RuntimeError('No fully closed candles available')
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f'{symbol}_{timeframe}'
    path = out_dir / f'{base}.csv'
    # No account details or credentials in export. Use a temp file then atomic replace.
    temp = out_dir / f'.{base}.csv.tmp'
    meta_path = out_dir / f'{base}.metadata.json'
    tmp_meta = out_dir / f'.{base}.metadata.json.tmp'
    if any(p.exists() or p.is_symlink() for p in (path, temp, meta_path, tmp_meta)):
        raise FileExistsError('Export destination exists; use a new output directory')
    with temp.open('x', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(('time_utc', 'open', 'high', 'low', 'close', 'tick_volume', 'spread_points'))
        for b in bars:
            writer.writerow((b.time.isoformat(), b.open, b.high, b.low,
                             b.close, b.volume, '' if b.spread is None else b.spread))
    digest = hashlib.sha256(temp.read_bytes()).hexdigest()
    metadata = {
        'symbol': symbol, 'timeframe': timeframe, 'collected_utc': collected_utc.isoformat(),
        'count': len(bars), 'start_utc': bars[0].time.isoformat(),
        'last_closed_utc': (bars[-1].time + timedelta(minutes=mins)).isoformat(),
        'sha256_csv': digest, 'price_basis': 'MT5 broker OHLC; validate bid/ask treatment',
        'requested_count': count, 'provider_count': returned_count,
        'excluded_unclosed_bars': returned_count - len(bars),
        'unclassified_gap_count': len(quality.gaps),
        'gap_samples': [{'missing_bars': g.missing_bars, 'duration_minutes': g.duration_minutes}
                        for g in quality.gaps[:10]],
        'timebase_status': 'TIMEBASE_UNVERIFIED', 'research_eligible': False,
        'account_mode': 'DEMO', 'read_only_gates_passed': True,
        'specifications_scope': 'CURRENT_SNAPSHOT_NOT_HISTORICAL_ECONOMICS',
        'symbol_specs_snapshot': {k: getattr(info, k, None) for k in
                                  ('digits', 'point', 'trade_tick_size', 'trade_tick_value',
                                   'trade_tick_value_profit', 'trade_tick_value_loss',
                                   'trade_contract_size', 'volume_min', 'volume_max',
                                   'volume_step', 'trade_stops_level', 'trade_calc_mode',
                                   'currency_profit', 'currency_margin')},
        'warnings': ['Rates availability varies by broker and terminal history',
                     'A symbol specification snapshot is not historical contract-spec data',
                     'Missing intervals are unclassified; no market closure inferred',
                     'UTC API convention does not independently attest the provider clock',
                     'Check broker licensing before redistribution'],
    }
    with tmp_meta.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False))
    validate_session(mt5, identity)
    # Hard links publish complete files without replacing a concurrent export.
    os.link(temp, path)
    os.link(tmp_meta, meta_path)
    temp.unlink()
    tmp_meta.unlink()
    return path, meta_path, metadata


def terminal_already_running(terminal):
    """Read process image paths; do not launch a saved terminal/account implicitly."""
    if sys.platform != 'win32' or not Path(terminal).is_file():
        return False
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        'Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path'],
        capture_output=True, text=True, timeout=10)
    expected = str(Path(terminal).resolve()).casefold()
    return any(str(Path(line.strip()).resolve()).casefold() == expected
               for line in result.stdout.splitlines() if line.strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', default='USTECH100M')
    parser.add_argument('--timeframe', choices=TIMEFRAMES, default='M5')
    parser.add_argument('--count', type=int, default=10000)
    parser.add_argument('--out-dir', type=Path, default=Path('data/nas100') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    parser.add_argument('--terminal', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    args = parser.parse_args(argv)
    mt5 = None
    initialized = False
    try:
        if not terminal_already_running(args.terminal):
            raise ExportSafetyError('TERMINAL_NOT_ALREADY_RUNNING', 'Expected terminal is not already running')
        import MetaTrader5 as mt5  # Optional Windows SDK; no import-time attachment
        initialized = bool(mt5.initialize(args.terminal, timeout=10000))
        if not initialized:
            raise ExportSafetyError('MT5_ATTACHMENT_FAILED', 'MT5 attachment failed')
        path, meta_path, metadata = export_closed_rates(
            mt5, symbol=args.symbol, timeframe=args.timeframe,
            count=args.count, out_dir=args.out_dir, collected_at=datetime.now(timezone.utc))
        print(json.dumps({'status': 'READ_ONLY_DEMO_EXPORT_UNVERIFIED', 'count': metadata['count'],
                          'csv': str(path), 'metadata': str(meta_path), 'research_eligible': False}))
        return 0
    except ExportSafetyError as exc:
        print(json.dumps({'status': 'BLOCKED_READ_ONLY_DEMO_EXPORT', 'reason': exc.code, 'research_eligible': False}))
        return 2
    except Exception:
        # SDK/OS exceptions may contain account details. Never echo them.
        print(json.dumps({'status': 'BLOCKED_READ_ONLY_DEMO_EXPORT', 'research_eligible': False}))
        return 2
    finally:
        if initialized and mt5 is not None:
            try:
                mt5.shutdown()
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
