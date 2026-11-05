"""Offline diagnostics for raw NAS100 exports. Never normalizes or predicts.

This is new local integration work, not a replacement for the missing Phase 2
review package. Raw epochs remain unverified even if they form an orderly grid.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from math import isfinite
from pathlib import Path

from bot.time_integrity import PERIOD_SECONDS


def audit_export(path: Path, timeframe: str, observed_at: datetime) -> dict:
    if timeframe not in PERIOD_SECONDS:
        raise ValueError('UNSUPPORTED_TIMEFRAME')
    if observed_at.utcoffset() is None:
        raise ValueError('OBSERVATION_MUST_BE_TIMEZONE_AWARE')
    payload = path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    if not rows:
        raise ValueError('EMPTY_DATASET')
    period = PERIOD_SECONDS[timeframe]
    if 'raw_time_epoch' in rows[0] and 'time_utc' not in rows[0]:
        time_column = 'raw_time_epoch'
        times = [int(row[time_column]) for row in rows]
    elif 'time_utc' in rows[0] and 'raw_time_epoch' not in rows[0]:
        # A column name is a declaration, not proof of actual UTC provenance.
        time_column = 'time_utc'
        stamps = [datetime.fromisoformat(row[time_column].replace('Z', '+00:00')) for row in rows]
        if any(stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0 or stamp.microsecond for stamp in stamps):
            raise ValueError('AMBIGUOUS_TIMESTAMP')
        times = [int(stamp.timestamp()) for stamp in stamps]
    else:
        raise ValueError('AMBIGUOUS_TIME_COLUMNS')
    invalid = 0
    for row in rows:
        o, h, l, c = (float(row[key]) for key in ('open', 'high', 'low', 'close'))
        if not (all(isfinite(x) and x > 0 for x in (o, h, l, c)) and l <= min(o, c) <= max(o, c) <= h):
            invalid += 1
    deltas = [b-a for a, b in zip(times, times[1:])]
    ordered = all(delta > 0 for delta in deltas)
    future = sum(stamp+period > observed_at.timestamp() for stamp in times)
    return {
        'file': path.name, 'sha256': hashlib.sha256(payload).hexdigest(),
        'timeframe': timeframe, 'time_column': time_column, 'rows': len(rows), 'invalid_ohlc': invalid,
        'strictly_ordered': ordered, 'duplicate_epochs': len(times)-len(set(times)),
        'first_raw_epoch': times[0], 'last_raw_epoch': times[-1],
        'interval_counts_seconds': dict(sorted(Counter(deltas).items())),
        'nonstandard_intervals': sum(delta != period for delta in deltas),
        'off_epoch_grid_bars': sum(stamp % period != 0 for stamp in times),
        'unclosed_or_future_against_observation': future,
        'observed_at_utc': observed_at.astimezone(timezone.utc).isoformat(),
        'timebase_status': 'TIMEBASE_UNVERIFIED',
        'research_eligible': False, 'model_trained': False,
        'signal_counts': None, 'performance': None,
        'blockers': ['INDEPENDENT_TIMEBASE_AND_SESSION_EVIDENCE_REQUIRED',
                     'EXECUTION_COST_AND_CONTRACT_HISTORY_UNVERIFIED'],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--timeframe', choices=sorted(PERIOD_SECONDS), required=True)
    parser.add_argument('--observed-at', help='Aware ISO observation time; default current UTC')
    args = parser.parse_args(argv)
    try:
        now = datetime.fromisoformat(args.observed_at.replace('Z', '+00:00')) if args.observed_at else datetime.now(timezone.utc)
        report = audit_export(args.input, args.timeframe, now)
    except (ValueError, KeyError, OSError, UnicodeError, OverflowError):
        print(json.dumps({'status': 'INVALID_OR_UNREADABLE_EXPORT', 'research_eligible': False}))
        return 2
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0  # diagnostic success is never research approval


if __name__ == '__main__':
    raise SystemExit(main())
