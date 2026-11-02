"""Fail-closed time eligibility and diagnostic price-based timeframe alignment.

No broker timezone or DST policy is inferred and no normalization is performed.
"""
from dataclasses import dataclass
from datetime import datetime
from math import isfinite, isclose

PERIOD_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800,
                  "H1": 3600, "H4": 14400, "D1": 86400}


class TimeIntegrityError(ValueError):
    pass


def utc_epoch(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise TimeIntegrityError("AMBIGUOUS_OR_INVALID_TIMESTAMP") from exc
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
        raise TimeIntegrityError("AMBIGUOUS_OR_NON_UTC_TIMESTAMP")
    return stamp.timestamp()


@dataclass(frozen=True)
class TimebaseEvidence:
    status: str
    source: str
    observed_at_utc: str
    timeframe: str
    grid_origin_epoch_seconds: int
    clock_uncertainty_seconds: float
    # Exact verified session gaps, not permission to skip arbitrary missing bars.
    allowed_gaps: tuple = ()


def require_verified_timebase(evidence):
    if not isinstance(evidence, TimebaseEvidence) or evidence.status != "VERIFIED_UTC":
        raise TimeIntegrityError("TIMEBASE_UNVERIFIED: independent UTC/DST evidence required")
    if not evidence.source or evidence.timeframe not in PERIOD_SECONDS:
        raise TimeIntegrityError("TIMEBASE_UNVERIFIED: source/timeframe required")
    if (isinstance(evidence.clock_uncertainty_seconds, bool) or
            not isfinite(evidence.clock_uncertainty_seconds) or evidence.clock_uncertainty_seconds < 0):
        raise TimeIntegrityError("Invalid clock uncertainty")
    if isinstance(evidence.grid_origin_epoch_seconds, bool) or not isinstance(evidence.grid_origin_epoch_seconds, int):
        raise TimeIntegrityError("Explicit UTC grid origin required")
    utc_epoch(evidence.observed_at_utc)


def validate_bar_times(candles, evidence):
    require_verified_timebase(evidence)
    if not candles:
        raise TimeIntegrityError("Empty time series")
    period = PERIOD_SECONDS[evidence.timeframe]
    # Earliest possible observation time, not a tolerance permitting future bars.
    latest_close = utc_epoch(evidence.observed_at_utc) - evidence.clock_uncertainty_seconds
    prior = None
    allowed_gaps = {(utc_epoch(start), utc_epoch(end)) for start, end in evidence.allowed_gaps}
    for candle in candles:
        opened = utc_epoch(candle.time_utc)
        if opened > latest_close:
            raise TimeIntegrityError("FUTURE_BAR")
        if opened + period > latest_close:
            raise TimeIntegrityError("INCOMPLETE_BAR")
        if (opened - evidence.grid_origin_epoch_seconds) % period:
            raise TimeIntegrityError("MISALIGNED_BAR_OPEN")
        if prior is not None:
            if opened <= prior:
                raise TimeIntegrityError("DUPLICATE_OR_UNORDERED_BAR")
            if opened != prior + period and (prior + period, opened) not in allowed_gaps:
                raise TimeIntegrityError("UNVERIFIED_SESSION_GAP_OR_MISSING_BAR")
        prior = opened


def alignment_report(lower, higher, lower_seconds, higher_seconds, relative_offset_seconds=0):
    """Compare high OHLC with exact lower-bar slots, in RAW time coordinates.

    Offset shifts lower timestamps only. A common offset cancels out, so even
    perfect matches cannot establish UTC or historical DST correctness.
    """
    if not lower or not higher or higher_seconds <= lower_seconds or higher_seconds % lower_seconds:
        raise TimeIntegrityError("Insufficient/invalid alignment input")
    if any(isinstance(row["time"], bool) or not isinstance(row["time"], int) for row in lower+higher):
        raise TimeIntegrityError("Ambiguous noninteger raw bar timestamp")
    times = [row["time"] + relative_offset_seconds for row in lower]
    high_times = [row["time"] for row in higher]
    if (len(set(times)) != len(times) or any(a >= b for a, b in zip(times, times[1:])) or
            len(set(high_times)) != len(high_times) or any(a >= b for a, b in zip(high_times, high_times[1:]))):
        raise TimeIntegrityError("Ambiguous duplicate/unordered alignment timestamps")
    indexed = dict(zip(times, lower))
    report = {"relative_lower_offset_seconds": relative_offset_seconds, "higher_windows": len(higher),
              "complete_windows": 0, "missing_windows": 0, "mismatch_windows": 0,
              "matching_windows": 0, "samples": [],
              "scope": "Relative raw-time OHLC alignment only; UTC/DST NOT established"}
    for row in higher:
        slots = range(row["time"], row["time"] + higher_seconds, lower_seconds)
        if any(slot not in indexed for slot in slots):
            report["missing_windows"] += 1
            continue
        parts = [indexed[slot] for slot in slots]
        aggregate = dict(open=parts[0]["open"], high=max(p["high"] for p in parts),
                         low=min(p["low"] for p in parts), close=parts[-1]["close"])
        match = all(isfinite(float(row[k])) and isfinite(float(aggregate[k])) and
                    isclose(float(row[k]), float(aggregate[k]), abs_tol=1e-8, rel_tol=0)
                    for k in aggregate)
        report["complete_windows"] += 1
        report["matching_windows" if match else "mismatch_windows"] += 1
        if len(report["samples"]) < 3:
            report["samples"].append({"higher_raw_open": row["time"], "lower_aggregate": aggregate,
                                      "higher_ohlc": {k: row[k] for k in aggregate}, "matches": match})
    return report


def require_complete_alignment(report):
    if not report["complete_windows"] or report["missing_windows"] or report["mismatch_windows"]:
        raise TimeIntegrityError("INCOMPLETE_OR_INCONSISTENT_TIMEFRAME_ALIGNMENT")
