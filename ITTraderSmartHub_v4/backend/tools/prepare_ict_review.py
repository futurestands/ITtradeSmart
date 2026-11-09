"""Prepare local blind annotations from an integrity-checked, ineligible CSV.

No training, execution, source rewriting, timestamp correction or data release.
The interactive HTML uses only its embedded review windows; no network calls.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from nas100.study_annotation import review_packet
from tools.run_nas100_research import read_candle_stream


def prepare(csv_path, expected_sha256, timeframe_minutes, review_stop, output_dir):
    csv_path, output_dir = Path(csv_path), Path(output_dir)
    if csv_path.is_symlink() or not csv_path.is_file() or not 0 < csv_path.stat().st_size <= 20_000_000:
        raise ValueError('Expected a bounded regular source CSV')
    raw = csv_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('SOURCE_HASH_MISMATCH')
    # Parse the exact bytes just hashed, not a second path read susceptible to
    # concurrent edits. This also keeps source provenance bound to the packet.
    bars = read_candle_stream(io.StringIO(raw.decode('utf-8-sig')), timeframe_minutes)
    packet = review_packet(bars, source_sha256=expected_sha256,
        timeframe_minutes=timeframe_minutes, review_stop=review_stop)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir/'review_packet.json').write_text(json.dumps(packet, indent=2, allow_nan=False)+'\n')
    template = (Path(__file__).with_name('ict_review_template.html')).read_text(encoding='utf-8')
    # Even an unexpected source value cannot terminate the JSON script element.
    embedded = json.dumps(packet, allow_nan=False).replace('<', '\\u003c')
    (output_dir/'review.html').write_text(template.replace('__REVIEW_PACKET_JSON__', embedded), encoding='utf-8')
    return {'status': 'BLIND_REVIEW_PREPARED_NOT_TRAINED', 'tasks': len(packet['tasks']),
        'packet_sha256': packet['packet_sha256'], 'source_sha256': expected_sha256,
        'training_eligible': False, 'decision': 'NO_TRADE', 'output_directory': str(output_dir)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--timeframe-minutes', type=int, required=True)
    p.add_argument('--review-stop', type=int, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.csv, a.expected_sha256, a.timeframe_minutes, a.review_stop, a.output_dir)))


if __name__ == '__main__': main()
