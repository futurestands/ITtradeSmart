"""Forensic analysis only: retains originals and never releases normalized data."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from bot.time_integrity import alignment_report, PERIOD_SECONDS, utc_epoch


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def comparisons(series):
    reports = {}
    for low, high in (("M15", "M30"), ("M15", "H1"), ("M15", "H4"), ("M30", "H1"), ("H1", "H4")):
        if not series.get(low) or not series.get(high):
            continue
        reports[low + "_to_" + high] = []
        for offset in (-7200, -3600, 0, 3600, 7200):
            # Exclude only windows outside joint acquisition coverage. Interior
            # missing slots remain failures, not silently filled/forward-filled.
            lower = series[low]
            higher = [r for r in series[high] if lower[0]["time"] + offset <= r["time"] and
                      r["time"] + PERIOD_SECONDS[high] <= lower[-1]["time"] + offset + PERIOD_SECONDS[low]]
            if not higher:
                reports[low + "_to_" + high].append({"offset_seconds": offset, "status": "NO_OVERLAP"})
                continue
            row = alignment_report(lower, higher, PERIOD_SECONDS[low], PERIOD_SECONDS[high], offset)
            row["excluded_outside_joint_coverage"] = len(series[high])-len(higher)
            reports[low + "_to_" + high].append(row)
    return reports


def analyze(root):
    directory = root / "evidence/time_integrity"
    original_files = sorted((root / "evidence").glob("*"))
    original_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in original_files if p.is_file()}
    old = {}
    for label in ("M15", "M30", "H1", "H4"):
        with (root / "evidence" / ("USTECH100M_" + label + ".csv")).open(encoding="utf-8", newline="") as handle:
            old[label] = [dict(time=int(utc_epoch(row["time_utc"])), **{k: float(row[k]) for k in
                               ("open", "high", "low", "close")}) for row in csv.DictReader(handle)]
    result = {"status": "TIMEBASE_UNVERIFIED", "research_eligible": False,
              "original_file_sha256": original_hashes, "original_relative_alignment": comparisons(old),
              "fresh_captures": [], "normalization": "NONE RELEASED; offsets below are diagnostic hypotheses only"}
    captures = []
    for path in sorted(directory.glob("capture_*/capture.json")):
        capture = json.loads(path.read_text(encoding="utf-8"))
        captures.append(capture)
        row = {"file": str(path.relative_to(root)), "capture_complete": capture.get("capture_complete", False),
               "quotes": [], "bar_heads": [], "specifications": [], "series": {}, "tick_to_bar": []}
        for call in capture["calls"]:
            value = call["value"]
            op = call["operation"]
            before, after = utc_epoch(call["observed_before_utc"]), utc_epoch(call["observed_after_utc"])
            if op == "terminal_state":
                row[op] = value
            if op.startswith("spec:"):
                row["specifications"].append(value)
            if op.startswith("tick:") and value:
                raw = value["time_msc"]/1000
                row["quotes"].append({"symbol": op.split(":")[1], "observed_before_utc": iso(before),
                    "observed_after_utc": iso(after), "raw_time": value["time"], "raw_time_msc": value["time_msc"],
                    "raw_epoch_rendered_as_utc_UNVERIFIED": iso(raw), "bid": value["bid"], "ask": value["ask"],
                    "raw_minus_windows_midpoint_seconds": raw-(before+after)/2,
                    "tested_server_offset_seconds_to_quote_age": {str(offset): (before+after)/2-(raw-offset)
                                                                     for offset in (0, 3600, 7200, 10800)}})
            if op.startswith("rates:") and value:
                label = op.split(":")[-1]
                row["series"][label] = value[:-1]  # exclude terminal position zero from comparisons
                row["bar_heads"].append({"timeframe": label, "position": "zero (forming, not research eligible)",
                    "observed_after_utc": iso(after), "raw_open": value[-1]["time"],
                    "raw_open_rendered_as_utc_UNVERIFIED": iso(value[-1]["time"]),
                    "hypotheses": [{"subtract_seconds": offset, "hypothetical_open_utc": iso(value[-1]["time"]-offset),
                        "hypothetical_close_utc": iso(value[-1]["time"]-offset+PERIOD_SECONDS[label])}
                                    for offset in (0, 3600, 7200, 10800)]})
        m15_calls = [c for c in capture["calls"] if c["operation"] == "rates:USTECH100M:M15" and c["value"]]
        if m15_calls and len(m15_calls[0]["value"]) >= 2:
            bar = m15_calls[0]["value"][-2]
            for call in capture["calls"]:
                if not call["operation"].startswith("ticks:"):
                    continue
                offset = int(call["operation"].split("_")[-1])
                ticks = [tick for tick in (call["value"] or []) if
                         bar["time"] + offset <= tick["time_msc"]/1000 < bar["time"] + offset + 900 and tick["bid"] > 0]
                item = {"operation": call["operation"], "bar_raw_open": bar["time"],
                        "tick_interval_relative_offset": offset, "returned_ticks": len(call["value"] or []),
                        "ticks_in_half_open_interval": len(ticks), "matches": False}
                if ticks:
                    aggregate = dict(open=ticks[0]["bid"], high=max(t["bid"] for t in ticks),
                                     low=min(t["bid"] for t in ticks), close=ticks[-1]["bid"])
                    item.update(tick_bid_ohlc=aggregate, bar_ohlc={k: bar[k] for k in aggregate},
                                matches=all(abs(aggregate[k]-bar[k]) < 1e-8 for k in aggregate))
                row["tick_to_bar"].append(item)
        row["relative_alignment"] = comparisons(row.pop("series"))
        row["relative_alignment_exclusion"] = "Terminal position zero removed from every timeframe; no complete-UTC eligibility implied"
        result["fresh_captures"].append(row)
    result["adjacent_capture_overlap"] = []
    for previous, current in zip(captures, captures[1:]):
        for label in ("M15", "M30", "H1", "H4"):
            a = next((c["value"][:-1] for c in previous["calls"] if c["operation"].endswith(":"+label)), [])
            b = next((c["value"][:-1] for c in current["calls"] if c["operation"].endswith(":"+label)), [])
            indexed = {r["time"]: r for r in b}
            common = [r for r in a if r["time"] in indexed]
            result["adjacent_capture_overlap"].append({"previous_started_utc": previous["started_utc"],
                "current_started_utc": current["started_utc"], "timeframe": label,
                "common_closed_bars": len(common), "unchanged_ohlc_same_raw_time": sum(
                    all(r[k] == indexed[r["time"]][k] for k in ("open", "high", "low", "close")) for r in common)})
    # Write only new milestone artifacts; old captures, reports and hashes untouched.
    with (directory / "analysis.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    eligibility = {"status": "TIMEBASE_UNVERIFIED", "research_eligible": False,
        "reason": "Absolute UTC mapping, historical broker DST and missing session intervals not independently established",
        "datasets": [{"file": name, "sha256": digest, "status": "TIMEBASE_UNVERIFIED",
                      "eligible_for_training_or_performance": False}
                     for name, digest in original_hashes.items() if name.startswith("USTECH100M_") and name.endswith(".csv")]}
    (directory / "dataset_eligibility.json").write_text(json.dumps(eligibility, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = analyze(Path(__file__).parent)
    print("TIMEBASE_UNVERIFIED; raw relative alignment diagnostics saved, no normalized dataset released.")
