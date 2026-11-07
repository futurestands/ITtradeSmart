"""Fit a local educational retriever; no market training, network or broker I/O."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from nas100.study_retrieval import canonical_hash, fit_study_index, retrieve_study


def corpus():
    reference = BACKEND/'research_reference'
    original = json.loads((reference/'ICT_STUDY_CATALOG_v1.json').read_text(encoding='utf-8'))
    supplement = json.loads((reference/'STUDY_PRIMARY_SUPPLEMENT_v1.json').read_text(encoding='utf-8'))
    cards = []
    for row in original['cards']:
        card = {'id': row['id'], 'title': row['id'].replace('-', ' '), 'kind': row['kind'],
                'note': row['note'], 'tags': row['terms'], 'url': None}
        if row['video_id']:
            card['url'] = f"https://www.youtube.com/watch?v={row['video_id']}&t={row['timestamp_seconds']}s"
        if 'implementation' in row:
            card['implementation'] = row['implementation']
        cards.append(card)
    return cards + supplement['cards']


def fit_and_save(output):
    cards = corpus()
    model = fit_study_index(cards)
    # Exclusive creation preserves previous trained artifacts and their evidence.
    with Path(output).open('x', encoding='utf-8') as handle:
        json.dump(model, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')
    return {'trained_at_utc': datetime.now(timezone.utc).isoformat(),
            'fit_calls': 1, 'fitted_component': 'TF_IDF_DOCUMENT_RETRIEVER',
            'documents': len(cards), 'vocabulary_features': len(model['idf']),
            'corpus_sha256': model['corpus_sha256'], 'artifact_sha256': model['artifact_sha256'],
            'file_sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest(),
            'market_models_trained': 0, 'lectures_ingested': 0,
            'decision': 'NO_TRADE', 'model_status': 'MODEL_NOT_READY',
            'execution_mode': 'RESEARCH_ONLY'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fit = sub.add_parser('fit')
    fit.add_argument('--output', type=Path, required=True)
    ask = sub.add_parser('query')
    ask.add_argument('--index', type=Path, required=True)
    ask.add_argument('question')
    args = parser.parse_args()
    if args.command == 'fit':
        result = fit_and_save(args.output)
    else:
        if args.index.stat().st_size > 5_000_000:
            raise ValueError('Index file exceeds supported size')
        index = json.loads(args.index.read_text(encoding='utf-8'))
        result = retrieve_study(index, args.question, expected_corpus_sha256=canonical_hash(corpus()))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
