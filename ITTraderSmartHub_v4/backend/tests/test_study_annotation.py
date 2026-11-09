import hashlib
import copy
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from nas100.candles import Candle
from nas100.study_annotation import review_packet, import_annotations
from tools.prepare_ict_review import prepare


def bars(count=300):
    start = datetime(2025, 1, 6, tzinfo=timezone.utc)
    return [Candle(start+timedelta(minutes=5*i), 100+i, 102+i, 99+i, 101+i) for i in range(count)]


def packet(rows=None, **changes):
    config = dict(source_sha256='a'*64, timeframe_minutes=5, review_stop=200,
                  lookback=20, stride=40, max_tasks=4)
    config.update(changes)
    return review_packet(bars() if rows is None else rows, **config)


def test_unseen_future_candles_cannot_change_review_packet():
    rows = bars()
    altered = rows[:200]+[replace(b, open=999999, high=1000001, low=999998, close=1000000) for b in rows[200:]]
    assert packet(rows) == packet(altered)


def test_each_chart_stops_at_its_own_close_and_has_no_outcome():
    result = packet()
    for task in result['tasks']:
        assert len(task['bars']) == 20
        assert task['label'] is None and task['human_reviewed'] is False
        assert task['outcome_supplied'] is False
        assert all(datetime.fromisoformat(b['declared_time_utc'])+timedelta(minutes=5)
                   <= datetime.fromisoformat(task['as_of_declared_utc']) for b in task['bars'])
    assert [t['anchor_index'] for t in result['tasks']] == [19, 59, 99, 139]


def test_missing_intervals_stay_visible_and_do_not_become_closures():
    rows = bars()
    rows = rows[:10]+[replace(b, time=b.time+timedelta(minutes=10)) for b in rows[10:]]
    result = packet(rows)
    assert result['tasks'][0]['unclassified_gaps'] == 1
    assert result['timebase_status'] == 'TIMEBASE_UNVERIFIED'
    assert result['session_labels_allowed'] is False
    assert result['training_eligible'] is False and result['trade_authorized'] is False


@pytest.mark.parametrize('change', [dict(review_stop=True), dict(review_stop=300),
    dict(review_stop=10), dict(stride=19), dict(lookback=False), dict(max_tasks=0),
    dict(timeframe_minutes=True), dict(source_sha256='unverified')])
def test_unsafe_review_configuration_is_rejected(change):
    with pytest.raises(ValueError): packet(**change)


def test_review_prefix_rejects_invalid_ohlc():
    rows = bars(); rows[8] = replace(rows[8], high=0)
    with pytest.raises(ValueError): packet(rows)


def source(tmp_path):
    path = tmp_path/'capture.csv'
    path.write_text('time_utc,open,high,low,close,tick_volume,spread_points\n'+
        ''.join(f'{b.time.isoformat()},{b.open},{b.high},{b.low},{b.close},10,2\n' for b in bars()))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_hash_mismatch_creates_nothing(tmp_path):
    path, digest = source(tmp_path)
    out = tmp_path/'packet'
    with pytest.raises(ValueError, match='SOURCE_HASH_MISMATCH'):
        prepare(path, '0'*64, 5, 200, out)
    assert not out.exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_preparation_preserves_source_and_never_overwrites_packet(tmp_path):
    path, digest = source(tmp_path)
    out = tmp_path/'packet'
    report = prepare(path, digest, 5, 200, out)
    assert report['training_eligible'] is False
    data = (out/'review_packet.json').read_bytes()
    result = json.loads(data)
    assert result['source_sha256'] == digest
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    html = (out/'review.html').read_text(encoding='utf-8')
    assert '__REVIEW_PACKET_JSON__' not in html and "connect-src 'none'" in html
    assert '400.0' not in html  # late-tail open price never enters the viewer
    with pytest.raises(FileExistsError): prepare(path, digest, 5, 200, out)
    assert (out/'review_packet.json').read_bytes() == data


def annotations(p):
    return dict(version='blind-ict-annotations-v1', packet_sha256=p['packet_sha256'],
        source_sha256=p['source_sha256'], timebase_status='TIMEBASE_UNVERIFIED',
        independently_reviewed=False, training_eligible=False, decision='NO_TRADE',
        annotations=[dict(task_id=p['tasks'][0]['task_id'], label='UNCERTAIN',
            reason='Synthetic test judgment, not a real human annotation.', lesson_reference='',
            invalidation_reason='', annotated_at_utc='2026-01-01T00:00:00+00:00', independently_reviewed=False)])


def ingest(p, a):
    return import_annotations(p, a, expected_packet_sha256=p['packet_sha256'],
                              observed_at=datetime(2026, 1, 2, tzinfo=timezone.utc))


def test_import_binds_source_and_never_promotes_review_or_training():
    p = packet(); a = annotations(p); result = ingest(p, a)
    assert result['records'][0]['anchor_index'] == p['tasks'][0]['anchor_index']
    assert result['training_eligible'] is False and result['independently_reviewed'] is False
    assert result['model_status'] == 'MODEL_NOT_READY' and result['decision'] == 'NO_TRADE'
    assert a == annotations(p)


@pytest.mark.parametrize('attack', ['wrong_source', 'wrong_packet', 'promote_training',
    'promote_review', 'duplicate_task', 'unknown_task', 'unknown_label', 'future_time', 'blank_reason'])
def test_import_rejects_wrong_provenance_and_annotation_claims(attack):
    p = packet(); a = annotations(p)
    if attack == 'wrong_source': a['source_sha256'] = 'b'*64
    elif attack == 'wrong_packet': a['packet_sha256'] = 'b'*64
    elif attack == 'promote_training': a['training_eligible'] = True
    elif attack == 'promote_review': a['annotations'][0]['independently_reviewed'] = True
    elif attack == 'duplicate_task': a['annotations'].append(copy.deepcopy(a['annotations'][0]))
    elif attack == 'unknown_task': a['annotations'][0]['task_id'] = 'b'*64
    elif attack == 'unknown_label': a['annotations'][0]['label'] = 'GUARANTEED_BUY'
    elif attack == 'future_time': a['annotations'][0]['annotated_at_utc'] = '2027-01-01T00:00:00Z'
    else: a['annotations'][0]['reason'] = ' '
    with pytest.raises(ValueError): ingest(p, a)


def test_changed_packet_cannot_reuse_original_integrity_pin():
    p = packet(); a = annotations(p); p['tasks'][0]['bars'][0]['close'] = 99999
    with pytest.raises(ValueError, match='PACKET_INTEGRITY_MISMATCH'): ingest(p, a)
