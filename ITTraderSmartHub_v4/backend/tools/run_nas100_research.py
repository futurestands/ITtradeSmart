"""Run an offline, unvalidated backtest over a broker CSV export.

Usage from backend:
 python tools/run_nas100_research.py --csv data/nas100/USTECH100M_M5.csv \
   --point-size 0.1 --spread-points 20 --start 500 --stop 1000

NOTE: --point-size and --spread-points must come from actual broker specs and a
conservative observed spread scenario; example numbers are placeholders only.
Never trade using a result from this utility. This is research, not a signal API.
"""
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import hashlib
from math import isclose
from pathlib import Path
from types import SimpleNamespace

# Direct-script execution sets sys.path to tools/, not backend/.
# Add the project backend root without installing any new package.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nas100 import Candle, validate_candles
from nas100.backtest import FillAssumptions
from nas100.research import run_research
from bot.time_integrity import TimebaseEvidence, validate_bar_times


def read_candles(path: Path, timeframe_minutes: int):
    data = []
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'time_utc', 'open', 'high', 'low', 'close', 'tick_volume', 'spread_points'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('CSV missing expected MT5 export columns')
        for row in reader:
            stamp = datetime.fromisoformat(row['time_utc'].replace('Z', '+00:00'))
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError('time_utc must be UTC')
            data.append(Candle(stamp, float(row['open']), float(row['high']),
                               float(row['low']), float(row['close']),
                               float(row['tick_volume']),
                               None if row['spread_points'] == '' else float(row['spread_points'])))
    validate_candles(data, timeframe_minutes)
    return data


def verify_real_dataset(csv_path, bars, timeframe_minutes, point_size, evidence_path, metadata_path,
                        symbol='USTECH100M'):
    """Reuse the existing application's clock/session eligibility gate.

    A manual evidence document is a local operator assertion, not a broker
    attestation. Validity permits unvalidated research only, never deployment.
    """
    if evidence_path is None:
        raise ValueError('TIMEBASE_UNVERIFIED')
    evidence = TimebaseEvidence(**json.loads(evidence_path.read_text(encoding='utf-8')))
    labels = {1: 'M1', 5: 'M5', 15: 'M15', 30: 'M30', 60: 'H1', 240: 'H4', 1440: 'D1'}
    if labels.get(timeframe_minutes) != evidence.timeframe:
        raise ValueError('TIMEFRAME_EVIDENCE_MISMATCH')
    validate_bar_times([SimpleNamespace(time_utc=b.time.isoformat()) for b in bars], evidence)
    if datetime.fromisoformat(evidence.observed_at_utc.replace('Z', '+00:00')) > datetime.now(timezone.utc):
        raise ValueError('FUTURE_OBSERVATION_EVIDENCE')
    metadata_path = metadata_path or csv_path.with_suffix('.metadata.json')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    if metadata.get('sha256_csv') != hashlib.sha256(csv_path.read_bytes()).hexdigest():
        raise ValueError('DATASET_HASH_MISMATCH')
    if (metadata.get('symbol') != symbol or metadata.get('timeframe') != labels[timeframe_minutes]
            or metadata.get('count') != len(bars) or metadata.get('account_mode') != 'DEMO'
            or metadata.get('read_only_gates_passed') is not True):
        raise ValueError('EXPORT_METADATA_MISMATCH')
    point = metadata['symbol_specs_snapshot']['point']
    if type(point) not in (int, float) or point <= 0 or not isclose(point, point_size, rel_tol=1e-12, abs_tol=0):
        raise ValueError('POINT_SIZE_MISMATCH')
    if any(b.spread is None for b in bars):
        raise ValueError('HISTORICAL_SPREAD_REQUIRED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--symbol', default='USTECH100M')
    parser.add_argument('--point-size', type=float, required=True)
    parser.add_argument('--spread-points', type=float, required=True)
    parser.add_argument('--slippage-points-per-side', type=float)
    parser.add_argument('--commission-points-round-trip', type=float)
    parser.add_argument('--base-minutes', type=int, default=5)
    parser.add_argument('--htf-minutes', type=int, default=60)
    parser.add_argument('--start', type=int, default=500)
    parser.add_argument('--stop', type=int)
    parser.add_argument('--stride', type=int, default=1)
    parser.add_argument('--max-inspections', type=int, default=2000)
    parser.add_argument('--timebase-evidence', type=Path)
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--synthetic-fixture', action='store_true',
                        help='Explicit synthetic smoke test only; never approves real-data performance')
    args = parser.parse_args(argv)
    bars = read_candles(args.csv, args.base_minutes)
    assumptions = FillAssumptions(
        point_size=args.point_size, spread_points=args.spread_points,
        slippage_points_per_side=0.0 if args.slippage_points_per_side is None else args.slippage_points_per_side,
        commission_points_round_trip=0.0 if args.commission_points_round_trip is None else args.commission_points_round_trip)
    if not args.synthetic_fixture:
        try:
            verify_real_dataset(args.csv, bars, args.base_minutes, args.point_size,
                                args.timebase_evidence, args.metadata, args.symbol)
        except Exception:
            print(json.dumps({'status': 'BLOCKED_DATASET_ELIGIBILITY', 'research_eligible': False,
                              'reason': 'VERIFIED_TIMEBASE_SESSION_HASH_AND_POINT_EVIDENCE_REQUIRED',
                              'decision_counts': None, 'summary': None}))
            return 2
        if args.slippage_points_per_side is None or args.commission_points_round_trip is None:
            print(json.dumps({'status': 'BLOCKED_COST_ASSUMPTIONS_REQUIRED', 'research_eligible': False,
                              'reason': 'EXPLICIT_SLIPPAGE_AND_COMMISSION_SCENARIOS_REQUIRED',
                              'decision_counts': None, 'summary': None}))
            return 2
    run = run_research(bars, args.base_minutes, args.htf_minutes,
                       assumptions, start=args.start, stop=args.stop,
                       stride=args.stride, max_inspections=args.max_inspections)
    result = {
        'status': 'RESEARCH_ONLY_UNVALIDATED', 'source': str(args.csv),
        'symbol': args.symbol,
        'sample_bars': len(bars), 'period_start_utc': bars[0].time.isoformat() if bars else None,
        'period_end_utc': bars[-1].time.isoformat() if bars else None,
        'inspections': run.inspected, 'signals': len(run.actionable),
        'decision_counts': dict(run.decision_counts),
        'source_kind': 'SYNTHETIC_FIXTURE_UNATTESTED' if args.synthetic_fixture else 'OPERATOR_EVIDENCE_RESEARCH_ONLY',
        'performance_validated': False, 'model_trained': False,
        'dataset_sha256': hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        'summary': asdict(run.summary), 'assumptions': asdict(assumptions),
        'notes': ['Not an investor return, forecast, win-rate claim, or trade instruction',
                  'Reference implementation is intentionally slow; no real-data study has been run by the author',
                  'OHLC ordering is unknown: stop-first for ambiguous bars',
                  'No broker order validation, market holidays, or trade execution'],
    }
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
    except Exception:
        print(json.dumps({'status': 'INVALID_RESEARCH_INPUT', 'research_eligible': False}))
        exit_code = 2
    raise SystemExit(exit_code)
