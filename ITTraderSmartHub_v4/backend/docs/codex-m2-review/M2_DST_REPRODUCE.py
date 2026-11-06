"""Offline evidence only: preserve raw epoch labels; never certify UTC.

Replay: python M2_DST_REPRODUCE.py --input <immutable-H1.csv> --out <review.json>
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input', type=Path, default=root.parent/'work/m2-smarthub/ITTraderSmartHub_v4/backend/evidence/USTECH100M_H1.csv')
parser.add_argument('--out', type=Path, default=root.parent/'outputs/M2_DST_REPRODUCTION.json')
args = parser.parse_args()
source = args.input
before = sha256(source.read_bytes()).hexdigest()
rows = list(csv.DictReader(source.open(encoding='utf-8')))
regimes = [('winter', '2025-12-02', '2026-03-06'),
           ('spring_US_EU_mismatch', '2026-03-09', '2026-03-27'),
           ('summer', '2026-03-30', '2026-10-23'),
           ('autumn_EU_US_mismatch', '2026-10-26', '2026-10-30')]
results = []
for name, first, last in regimes:
    selected = [r for r in rows if first <= r['time_utc'][:10] <= last
                and datetime.fromisoformat(r['time_utc']).weekday() < 5]
    groups = defaultdict(list)
    for r in selected:
        groups[datetime.fromisoformat(r['time_utc']).hour].append(float(r['high'])-float(r['low']))
    scale = median(float(r['high'])-float(r['low']) for r in selected)
    hourly = {str(hour): mean(values)/scale for hour, values in sorted(groups.items())}
    peak = max(hourly, key=hourly.get)
    results.append(dict(regime=name, first=first, last=last, bars=len(selected),
                        observed_days=len({r['time_utc'][:10] for r in selected}),
                        peak_raw_label_hour=int(peak), normalized_peak=round(hourly[peak], 4),
                        hourly_mean_range_over_regime_median=hourly))
after = sha256(source.read_bytes()).hexdigest()
assert before == after
report = dict(source=source.name, sha256_before=before, sha256_after=after,
              rows=len(rows), raw_epochs_preserved=True, corrected_dataset_created=False,
              timebase_status='TIMEBASE_UNVERIFIED', research_eligible=False,
              method='Weekday mean high-low by raw label hour / regime median bar high-low',
              limitation='Activity peaks are a heuristic, not independent clock evidence; incomplete days retained.',
              regimes=results)
out = args.out
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='regimes'}))
for r in results:
    print(json.dumps({k:v for k,v in r.items() if not k.startswith('hourly')}))
