"""One integrity-pinned evidence artifact; never reads local worker directories."""
from pathlib import Path
from paper_trial_contract import read_snapshot

BUNDLE_FILE=Path(__file__).resolve().parent/'research_bundle/paper_trial_snapshot.json'
EXPECTED_SHA256='a19ba4d1c70afbd6bc66710e813e12e1942d3db85a65efc15674924a2e003d50'


def published_paper_snapshot():
    return read_snapshot(BUNDLE_FILE,EXPECTED_SHA256)
