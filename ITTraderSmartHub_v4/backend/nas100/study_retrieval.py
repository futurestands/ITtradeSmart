"""Fitted TF-IDF knowledge retrieval, independent of predictive/execution systems.

Learns corpus document frequencies, never market labels or an execution policy.
JSON artifacts contain data only; no pickle or dynamic code loading.
"""
from collections import Counter
import hashlib
import json
from math import isfinite, log, sqrt
import re

VERSION = 'study-tfidf-v1'
KINDS = frozenset({'OFFICIAL_VIDEO_METADATA', 'PRIMARY_SOURCE_SUMMARY',
                   'IMPLEMENTATION_HYPOTHESIS', 'RESEARCH_PROTOCOL', 'USER_POLICY'})
STOP = frozenset('a an and are as at be by can do does for from how i in is it me my of on or our should the this to we what when which why with you your'.split())


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def terms(text):
    words = [w for w in re.findall(r'[a-z0-9]+(?:\.[0-9]+)?', text.lower()) if w not in STOP]
    return words + [a + ' ' + b for a, b in zip(words, words[1:])]


def _validated(cards):
    if not isinstance(cards, list) or not 1 <= len(cards) <= 1000:
        raise ValueError('Provide between 1 and 1000 curated cards')
    ids = set()
    for card in cards:
        if (not isinstance(card, dict) or not isinstance(card.get('id'), str)
                or not card['id'] or card['id'] in ids or card.get('kind') not in KINDS):
            raise ValueError('Invalid, duplicate or unreviewed card provenance')
        ids.add(card['id'])
        if any(not isinstance(card.get(key), str) or not card[key].strip() or len(card[key]) > 10000 for key in ('title', 'note')):
            raise ValueError('Invalid card text')
        if not isinstance(card.get('tags'), list) or any(not isinstance(t, str) for t in card['tags']):
            raise ValueError('Invalid card tags')
        if card['kind'] in {'PRIMARY_SOURCE_SUMMARY', 'OFFICIAL_VIDEO_METADATA'}:
            if not isinstance(card.get('url'), str):
                raise ValueError('Primary evidence needs a source URL')
            # Exact HTTPS authority matching needs no URL/network library.
            # User-info, alternate ports and suffix lookalikes do not match.
            origin = re.fullmatch(r'https://([^/?#\s]+)(?:[/?#]\S*)?', card['url'])
            if origin is None or origin.group(1) not in {
                'www.youtube.com', 'youtube.com', 'www.theinnercircletrader.com',
                'theinnercircletrader.com', 'www.mql5.com', 'ftmo.com', 'www.cmegroup.com'}:
                raise ValueError('Unapproved primary-source location')


def _text(card):
    return card['title'] + ' ' + ' '.join(card['tags']) + ' ' + card['note']


def _vector(text, idf):
    counts = Counter(t for t in terms(text) if t in idf)
    weighted = {t: (1 + log(n)) * idf[t] for t, n in counts.items()}
    norm = sqrt(sum(w*w for w in weighted.values()))
    return {t: w/norm for t, w in weighted.items()} if norm else {}


def fit_study_index(cards):
    """Fit vocabulary/IDF on curated documents ONLY, not evaluation questions."""
    _validated(cards)
    frequency = Counter()
    for card in cards:
        frequency.update(set(terms(_text(card))))
    if not frequency or len(frequency) > 50000:
        raise ValueError('Empty or excessive vocabulary')
    idf = {t: log((1+len(cards))/(1+n)) + 1 for t, n in sorted(frequency.items())}
    payload = {'version': VERSION, 'corpus_sha256': canonical_hash(cards),
               'cards': cards, 'idf': idf,
               'vectors': [_vector(_text(card), idf) for card in cards],
               'learning_scope': 'UNSUPERVISED_DOCUMENT_FREQUENCIES_ONLY'}
    return {**payload, 'artifact_sha256': canonical_hash(payload)}


def validate_index(index):
    if not isinstance(index, dict) or index.get('version') != VERSION:
        raise ValueError('Unsupported index version')
    payload = {key: value for key, value in index.items() if key != 'artifact_sha256'}
    if index.get('artifact_sha256') != canonical_hash(payload):
        raise ValueError('Index integrity check failed')
    _validated(index['cards'])
    if canonical_hash(index['cards']) != index['corpus_sha256']:
        raise ValueError('Corpus hash mismatch')
    idf, vectors = index['idf'], index['vectors']
    if (not isinstance(idf, dict) or not 1 <= len(idf) <= 50000
            or len(vectors) != len(index['cards'])):
        raise ValueError('Invalid fitted dimensions')
    for term, value in idf.items():
        if not isinstance(term, str) or type(value) not in (float, int) or not isfinite(value) or value < 1:
            raise ValueError('Invalid fitted weight')
    for vector in vectors:
        if not isinstance(vector, dict) or any(t not in idf or type(v) not in (float, int)
                or not isfinite(v) or v < 0 for t, v in vector.items()):
            raise ValueError('Invalid fitted vector')
        if vector and abs(sum(v*v for v in vector.values()) - 1) > 1e-8:
            raise ValueError('Invalid vector norm')


def retrieve_study(index, query, *, limit=3, expected_corpus_sha256=None):
    validate_index(index)
    if expected_corpus_sha256 is not None and expected_corpus_sha256 != index['corpus_sha256']:
        raise ValueError('Sources changed: rebuild and review index')
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError('Query must have 1 to 1000 characters')
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('Invalid result limit')
    vector = _vector(query, index['idf'])
    ranked = []
    for card, trained in zip(index['cards'], index['vectors']):
        score = sum(v * trained.get(t, 0) for t, v in vector.items())
        if score >= .15:  # Fixed retrieval cutoff, not a trading threshold.
            ranked.append({'card': card, 'similarity': score})
    matches = sorted(ranked, key=lambda row: (-row['similarity'], row['card']['id']))[:limit]
    return {'status': 'STUDY_NOTES_FOUND' if matches else 'NO_CURATED_EVIDENCE',
            'matches': matches, 'corpus_sha256': index['corpus_sha256'],
            'scope': 'FITTED_TEXT_RETRIEVAL_NOT_MARKET_PREDICTION',
            'similarity_is_probability': False, 'current_account_rules_verified': False,
            'model_status': 'MODEL_NOT_READY', 'execution_mode': 'RESEARCH_ONLY',
            'decision': 'NO_TRADE', 'trade_authorized': False,
            'limitations': ['No full ICT lectures ingested', 'Notes are dated; rules require fresh account-specific verification',
                            'Source URLs and hashes are provenance, not a guarantee of truth',
                            'Lexical similarity does not establish semantic correctness or trading skill']}
