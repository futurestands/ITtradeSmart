"""Validate local chart annotations for subsequent review, never model fitting."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nas100.study_annotation import import_annotations


def read_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 5_000_000:
        raise ValueError('Expected a bounded regular JSON file')
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    def reject(_): raise ValueError('Nonfinite JSON value')
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique, parse_constant=reject)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--expected-packet-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = import_annotations(read_json(args.packet), read_json(args.annotations),
        expected_packet_sha256=args.expected_packet_sha256, observed_at=datetime.now(timezone.utc))
    with args.out.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': 'ANNOTATIONS_IMPORTED_FOR_REVIEW_ONLY',
        'records': len(result['records']), 'training_eligible': False, 'decision': 'NO_TRADE'}))


if __name__ == '__main__': main()
