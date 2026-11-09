"""Blind chart-review packets, without outcomes, session claims or training.

Source timestamps remain declarations until independently certified. Human
setup judgments are annotations, never a permission to fit or execute a model.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from .candles import validate_candles

LABELS = ('LONG_SETUP_HYPOTHESIS', 'SHORT_SETUP_HYPOTHESIS', 'NO_SETUP', 'UNCERTAIN')


def review_packet(candles, *, source_sha256, timeframe_minutes, review_stop,
                  lookback=96, stride=128, max_tasks=12):
    """Choose systematic anchors strictly before an explicit sealed-tail cutoff.

    Only the review prefix is inspected. Each task contains history through its
    anchor's close and no later bars, outcome or generated correct answer.
    """
    if not isinstance(source_sha256, str) or not re.fullmatch('[0-9a-f]{64}', source_sha256):
        raise ValueError('Verified source SHA-256 required')
    for name, value, minimum, maximum in (
        ('timeframe', timeframe_minutes, 1, 1440), ('lookback', lookback, 20, 500),
        ('stride', stride, 1, 10000), ('tasks', max_tasks, 1, 100)):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError('Invalid '+name)
    if type(review_stop) is not int or not lookback <= review_stop < len(candles):
        raise ValueError('Explicit review cutoff must leave a sealed tail')
    if stride < lookback:
        raise ValueError('Review windows must not overlap')
    prefix = candles[:review_stop]
    validate_candles(prefix, timeframe_minutes)
    span = timedelta(minutes=timeframe_minutes)
    tasks = []
    for anchor in range(lookback-1, review_stop, stride):
        window = prefix[anchor-lookback+1:anchor+1]
        material = f'blind-ict-review-v1:{source_sha256}:{timeframe_minutes}:{anchor}:{lookback}'
        tasks.append({
            'task_id': hashlib.sha256(material.encode()).hexdigest(),
            'anchor_index': anchor,
            'as_of_declared_utc': (window[-1].time+span).isoformat(),
            'unclassified_gaps': sum(b.time-a.time != span for a, b in zip(window, window[1:])),
            'bars': [{'declared_time_utc': b.time.isoformat(), 'open': b.open,
                      'high': b.high, 'low': b.low, 'close': b.close} for b in window],
            'label': None, 'human_reviewed': False, 'outcome_supplied': False,
        })
        if len(tasks) == max_tasks:
            break
    payload = {
        'version': 'blind-ict-review-v1', 'source_sha256': source_sha256,
        'timeframe_minutes': timeframe_minutes, 'review_stop_exclusive': review_stop,
        'sealed_tail_rows': len(candles)-review_stop, 'selection': 'SYSTEMATIC_NONOVERLAPPING_WINDOWS',
        'timebase_status': 'TIMEBASE_UNVERIFIED', 'session_labels_allowed': False,
        'training_eligible': False, 'model_status': 'MODEL_NOT_READY',
        'decision': 'NO_TRADE', 'trade_authorized': False,
        'labels': list(LABELS), 'tasks': tasks,
        'instructions': [
            'Judge only the visible chart; do not inspect the source file or later bars.',
            'Record setup hypotheses, invalidation reasoning and lesson references, including failed/no-setup cases.',
            'Do not assign clock-dependent sessions or news context while the source timebase is unverified.',
            'Leave uncertain cases UNCERTAIN; no answer, performance or market edge is generated.',
            'The sealed tail is reserved from this review packet, not certified as an untouched final model holdout.',
        ],
    }
    payload['packet_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return payload


def import_annotations(packet, document, *, expected_packet_sha256, observed_at):
    """Bind returned judgments to the original packet, without certifying labels."""
    if not isinstance(packet, dict) or not isinstance(document, dict):
        raise ValueError('Packet and annotation objects required')
    original = {k: v for k, v in packet.items() if k != 'packet_sha256'}
    calculated = hashlib.sha256(json.dumps(original, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    if calculated != expected_packet_sha256 or packet.get('packet_sha256') != calculated:
        raise ValueError('PACKET_INTEGRITY_MISMATCH')
    keys = {'version', 'packet_sha256', 'source_sha256', 'annotations', 'timebase_status',
            'independently_reviewed', 'training_eligible', 'decision'}
    if set(document) != keys or document['version'] != 'blind-ict-annotations-v1':
        raise ValueError('Unsupported annotation document')
    if (document['packet_sha256'] != calculated or document['source_sha256'] != packet['source_sha256']
            or document['timebase_status'] != 'TIMEBASE_UNVERIFIED'
            or document['independently_reviewed'] is not False
            or document['training_eligible'] is not False or document['decision'] != 'NO_TRADE'):
        raise ValueError('ANNOTATION_PROVENANCE_OR_SAFETY_MISMATCH')
    if (not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or observed_at.utcoffset() != timedelta(0)):
        raise ValueError('UTC import observation required')
    rows = document['annotations']
    if not isinstance(rows, list) or not 1 <= len(rows) <= len(packet['tasks']):
        raise ValueError('One to the packet task count of annotations required')
    tasks = {t['task_id']: t for t in packet['tasks']}
    seen, records = set(), []
    row_keys = {'task_id', 'label', 'reason', 'lesson_reference', 'invalidation_reason',
                'annotated_at_utc', 'independently_reviewed'}
    for row in rows:
        if not isinstance(row, dict) or set(row) != row_keys:
            raise ValueError('Unsupported annotation fields')
        if (not isinstance(row['task_id'], str) or row['task_id'] not in tasks
                or row['task_id'] in seen or row['label'] not in LABELS
                or row['independently_reviewed'] is not False):
            raise ValueError('Unknown, duplicate or promoted annotation')
        for key, limit in (('reason', 4000), ('lesson_reference', 1000), ('invalidation_reason', 1000)):
            if not isinstance(row[key], str) or len(row[key]) > limit:
                raise ValueError('Invalid annotation text')
        if not row['reason'].strip() or not isinstance(row['annotated_at_utc'], str):
            raise ValueError('Reason and annotation time required')
        stamp = datetime.fromisoformat(row['annotated_at_utc'].replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0) or stamp > observed_at:
            raise ValueError('Invalid or future annotation time')
        seen.add(row['task_id'])
        records.append({**row, 'anchor_index': tasks[row['task_id']]['anchor_index'],
            'as_of_declared_utc': tasks[row['task_id']]['as_of_declared_utc']})
    return {'version': 'ict-review-import-v1', 'packet_sha256': calculated,
        'source_sha256': packet['source_sha256'], 'records': records,
        'imported_at_utc': observed_at.astimezone(timezone.utc).isoformat(),
        'annotation_origin': 'LOCAL_OPERATOR_CLAIM_NOT_INDEPENDENTLY_VERIFIED',
        'timebase_status': 'TIMEBASE_UNVERIFIED', 'independently_reviewed': False,
        'training_eligible': False, 'model_status': 'MODEL_NOT_READY', 'decision': 'NO_TRADE'}
