"""Bounded synthetic rule-engine contract demonstration; never a market signal.

No file, SDK, network, estimator or caller-supplied prices are consumed. Fixture
timestamps are invented UTC and carry no evidence about a broker's timebase.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from nas100.analysis import analyze
from nas100.candles import Candle
from nas100.sessions import session_state


def synthetic_preview():
    start = datetime(2024, 3, 11, 8, tzinfo=timezone.utc)
    bars = []
    for i in range(96):
        # Integer arithmetic keeps this fixture stable across platforms.
        opening = 10000 + i * 2 + (i % 12 if (i // 12) % 2 == 0 else 12 - i % 12) * 5
        close = opening + (3 if i % 3 else -4)
        bars.append(Candle(start + timedelta(minutes=5*i), opening,
                           max(opening, close)+6, min(opening, close)-6, close, 100, 0))
    result = analyze(bars, 5)
    digest = sha256(json.dumps([
        [b.time.isoformat(), b.open, b.high, b.low, b.close, b.volume, b.spread]
        for b in bars
    ], separators=(',', ':')).encode()).hexdigest()
    return {
        'schema': 'nas100-synthetic-research-preview-v1',
        'decision': 'NO_TRADE', 'probability': None, 'model_status': 'MODEL_NOT_READY',
        'execution_enabled': False,
        'data': {'dataset_id': 'synthetic-integer-fixture-v1', 'sha256': digest,
                 'is_synthetic': True, 'research_eligible': False,
                 'freshness': 'FIXED_OFFLINE_FIXTURE_NOT_LIVE',
                 'timebase_status': 'SYNTHETIC_UTC_NOT_BROKER_EVIDENCE',
                 'as_of': result.as_of.isoformat()},
        'analysis': {'bars': len(bars), 'timeframe_minutes': 5,
                     'status': result.status, 'trend': result.trend,
                     'structure_event_count': len(result.events),
                     'fvg_count': len(result.fvgs), 'sweep_count': len(result.sweeps),
                     'sessions_at_as_of': asdict(session_state(result.as_of))},
        'reasons': ['SYNTHETIC_DEMONSTRATION_ONLY', 'NO_VALIDATED_REAL_MARKET_MODEL',
                    'REAL_DATA_ELIGIBILITY_UNRESOLVED'],
        'invalidation': ['Never use this fixture for a market decision.',
                         'Any real-data replacement needs independent provenance, UTC, costs and model review.'],
    }
