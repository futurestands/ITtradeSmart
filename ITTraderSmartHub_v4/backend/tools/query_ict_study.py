"""Retrieve locally curated study notes. No LLM, model fitting, network or trades."""
import argparse
import hashlib
import json
from pathlib import Path
import re

CATALOG = Path(__file__).resolve().parents[1] / 'research_reference' / 'ICT_STUDY_CATALOG_v1.json'
KINDS = {'OFFICIAL_VIDEO_METADATA', 'IMPLEMENTATION_HYPOTHESIS', 'RESEARCH_PROTOCOL', 'USER_POLICY'}


def query_study(query, *, limit=3):
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError('Provide a nonempty study query of at most 1000 characters')
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('limit must be between 1 and 10')
    raw = CATALOG.read_bytes()
    catalog = json.loads(raw)
    # This local catalogue contains metadata and original research notes only.
    # Unsupported provenance must never acquire a fabricated verified status.
    if any(card['kind'] not in KINDS for card in catalog['cards']):
        raise ValueError('Unsupported source status')
    words = set(re.findall(r'[a-z0-9]+', query.lower()))
    ranked = []
    for card in catalog['cards']:
        vocabulary = set(re.findall(r'[a-z0-9]+', ' '.join(card['terms'])))
        score = len(words & vocabulary)
        if score:
            result = {**card, 'matched_terms': sorted(words & vocabulary)}
            result.pop('terms')
            if card['video_id']:
                result['source_url'] = f"https://www.youtube.com/watch?v={card['video_id']}&t={card['timestamp_seconds']}s"
            ranked.append((score, card['id'], result))
    matches = [row[2] for row in sorted(ranked, key=lambda row: (-row[0], row[1]))[:limit]]
    return {
        'status': 'STUDY_NOTES_FOUND' if matches else 'NO_CURATED_EVIDENCE',
        'matches': matches, 'catalog_sha256': hashlib.sha256(raw).hexdigest(),
        'method': 'TOKEN_OVERLAP_RETRIEVAL_NOT_TRAINED_MODEL',
        'full_lectures_ingested': 0, 'models_fitted': 0,
        'execution_mode': 'RESEARCH_ONLY', 'model_status': 'MODEL_NOT_READY',
        'decision': 'NO_TRADE', 'trade_authorized': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query')
    args = parser.parse_args()
    print(json.dumps(query_study(args.query), indent=2))
