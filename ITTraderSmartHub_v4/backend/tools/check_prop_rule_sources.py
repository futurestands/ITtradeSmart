"""On-demand public official-source research, no account data and no approval."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prop_rule_research import SOURCES, fingerprint_source

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=sorted(SOURCES), required=True)
    args = parser.parse_args()
    print(json.dumps(fingerprint_source(args.source), indent=2))
