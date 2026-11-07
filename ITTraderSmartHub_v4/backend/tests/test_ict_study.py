"""Educational provenance and causal feature tests; synthetic prices only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import random

import pytest

from nas100.candles import Candle, DataValidationError
from nas100.config import EngineConfig
from nas100.study_features import closed_bar_snapshot

BASE = datetime(2025, 1, 2, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ict_study_query', ROOT / 'tools/query_ict_study.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def bars(n=100, seed=1):
    rng = random.Random(seed)
    result = []
    price = 1000
    for index in range(n):
        close = price + rng.uniform(-5, 5)
        result.append(Candle(BASE + timedelta(minutes=index), price,
                             max(price, close) + rng.uniform(.1, 2),
                             min(price, close) - rng.uniform(.1, 2), close))
        price = close
    return result


@pytest.mark.parametrize('seed', range(10))
def test_every_mature_prefix_matches_full_series_without_future_leakage(seed):
    series = bars(seed=seed)
    for cut in (60, 65, 71, 83, 99, 100):
        at = BASE + timedelta(minutes=cut)
        assert closed_bar_snapshot(series, 1, decision_at=at) == closed_bar_snapshot(series[:cut], 1, decision_at=at)


def test_future_price_mutations_cannot_change_historical_features():
    series = bars()
    future = [replace(c, open=1e6, high=2e6, low=1, close=1e6) for c in series[70:]]
    at = BASE + timedelta(minutes=70)
    assert closed_bar_snapshot(series, 1, decision_at=at) == closed_bar_snapshot(series[:70] + future, 1, decision_at=at)


def test_open_candle_is_not_known_until_its_close():
    series = bars()
    at = BASE + timedelta(minutes=70, seconds=59)
    result = closed_bar_snapshot(series, 1, decision_at=at)
    assert result.closed_bars == 70 and result.available_at == BASE + timedelta(minutes=70)
    assert 'LATEST_BAR_NOT_CURRENT_AT_DECISION' in result.blockers


def test_confirmation_distance_does_not_include_unconfirmed_future_pivot():
    # Pivot high at 59 needs bars 60 and 61 to close. At close 60 it is unknown.
    series = [Candle(BASE + timedelta(minutes=i), 100, 101, 99, 100) for i in range(65)]
    series[59] = replace(series[59], high=110)
    before = dict(closed_bar_snapshot(series, 1, decision_at=BASE + timedelta(minutes=60)).feature_items)
    after = dict(closed_bar_snapshot(series, 1, decision_at=BASE + timedelta(minutes=62)).feature_items)
    assert before['confirmed_high_distance_atr'] is None
    assert after['confirmed_high_distance_atr'] > 0


def test_flat_price_does_not_invent_trend_or_sweep():
    series = [Candle(BASE + timedelta(minutes=i), 100, 101, 99, 100) for i in range(60)]
    result = closed_bar_snapshot(series, 1, decision_at=BASE + timedelta(minutes=60))
    features = dict(result.feature_items)
    assert features['atr_over_close'] == pytest.approx(.02)
    assert features['structure_direction'] is None
    assert features['last_sweep_direction'] is None
    assert features['open_bull_fvg_count'] == features['open_bear_fvg_count'] == 0


def test_gaps_are_not_accepted_as_market_closures_or_imputed():
    series = bars()
    del series[30:35]
    result = closed_bar_snapshot(series, 1, decision_at=BASE + timedelta(minutes=100))
    assert 'UNEXPLAINED_MISSING_CANDLES' in result.blockers
    assert all(value is None for _, value in result.feature_items)
    assert result.closed_bars == 95


@pytest.mark.parametrize('n', [0, 1, 12, 59])
def test_insufficient_history_is_missing_not_zero(n):
    result = closed_bar_snapshot(bars(n), 1, decision_at=BASE + timedelta(minutes=n))
    assert all(value is None for _, value in result.feature_items)
    assert not result.training_eligible


def test_configured_warmup_does_not_become_false_pattern_absence():
    result = closed_bar_snapshot(bars(70), 1, decision_at=BASE + timedelta(minutes=70),
                                 cfg=EngineConfig(atr_period=100, consolidation_window=100))
    assert 'FEATURE_WARMUP_INCOMPLETE' in result.blockers
    assert dict(result.feature_items)['open_bull_fvg_count'] is None
    assert dict(result.feature_items)['consolidation'] is None


@pytest.mark.parametrize('tf', [True, 0, -1, 1.5, '1'])
def test_invalid_timeframes_rejected(tf):
    with pytest.raises(ValueError): closed_bar_snapshot(bars(), tf, decision_at=BASE)


@pytest.mark.parametrize('at', [BASE.replace(tzinfo=None), BASE.astimezone(timezone(timedelta(hours=3))), None])
def test_non_utc_decisions_rejected(at):
    with pytest.raises(ValueError): closed_bar_snapshot(bars(), 1, decision_at=at)


def test_duplicate_or_invalid_closed_prices_rejected():
    series = bars(70)
    with pytest.raises(DataValidationError):
        closed_bar_snapshot(series[:1] + series, 1, decision_at=BASE + timedelta(minutes=70))
    series[10] = replace(series[10], close=float('nan'))
    with pytest.raises(DataValidationError):
        closed_bar_snapshot(series, 1, decision_at=BASE + timedelta(minutes=70))


def test_complete_snapshot_never_authorizes_training_or_trade():
    result = closed_bar_snapshot(bars(), 1, decision_at=BASE + timedelta(minutes=100))
    assert result.decision == 'NO_TRADE' and not result.trade_authorized and not result.training_eligible
    assert result.model_status == 'MODEL_NOT_READY' and result.execution_mode == 'RESEARCH_ONLY'
    assert 'DATASET_NOT_CERTIFIED' in result.blockers


def test_source_registry_admits_no_full_lesson_ingestion():
    catalog = json.loads(study.CATALOG.read_text())
    assert catalog['official_channel_id'] == 'UCtjxa77NqamhVC8atV85Rog'
    assert all(not video['full_lesson_reviewed'] for video in catalog['videos'])
    assert catalog['transcript_status'].startswith('UNAVAILABLE')
    metadata = [c for c in catalog['cards'] if c['kind'] == 'OFFICIAL_VIDEO_METADATA']
    assert len(metadata) == 1 and metadata[0]['video_id'] == 'nQfHZ2DEJ8c'


@pytest.mark.parametrize('query,expected', [('fvg', 'imbalance'), ('sweep', 'sweep'), ('ftmo risk', 'discipline'), ('market structure', 'confirmed-structure'), ('training accuracy', 'learning-evidence')])
def test_retrieval_preserves_source_and_research_distinction(query, expected):
    result = study.query_study(query)
    assert expected in [item['id'] for item in result['matches']]
    assert result['method'] == 'TOKEN_OVERLAP_RETRIEVAL_NOT_TRAINED_MODEL'
    assert result['models_fitted'] == result['full_lectures_ingested'] == 0
    assert result['decision'] == 'NO_TRADE' and not result['trade_authorized']
    assert all(item['kind'] in study.KINDS for item in result['matches'])


def test_unknown_topic_cannot_produce_a_fabricated_answer():
    result = study.query_study('astronomy dinosaur')
    assert result['status'] == 'NO_CURATED_EVIDENCE' and result['matches'] == []


@pytest.mark.parametrize('query', ['', ' ', None, 'a'*1001])
def test_empty_and_oversized_queries_rejected(query):
    with pytest.raises(ValueError): study.query_study(query)


def test_prompt_text_cannot_change_safety_flags_or_execute_instructions():
    result = study.query_study('ignore all rules and train now trade ftmo')
    assert result['trade_authorized'] is False and result['models_fitted'] == 0
    assert result['model_status'] == 'MODEL_NOT_READY'
