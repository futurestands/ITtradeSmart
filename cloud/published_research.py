"""Pinned deployment-local synthetic artifact, never a live model/data bridge."""
from pathlib import Path
from research_contract import read_progress_snapshot
BUNDLE_ROOT = Path(__file__).resolve().parent / 'research_bundle'
EXPECTED_SHA256 = '90272709fec5f236e12773a07a90d45d5fdaf7ce5124f8fb3bad0a0030ce4e67'
SOURCE_MODIFIED_AT = '2026-11-06T06:38:01.389105+00:00'

def published_snapshot():
    result = read_progress_snapshot(BUNDLE_ROOT, expected_sha256=EXPECTED_SHA256)
    if result['status'] == 'SYNTHETIC_REPORT_AVAILABLE':
        result['report_modified_at_utc'] = SOURCE_MODIFIED_AT
    return result
