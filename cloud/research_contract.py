"""Read-only NAS100 synthetic research snapshot for the SmartHub dashboard.

This module reads one explicitly configured *local* Lab report filename.
It never imports a model, authentic-market data, broker services or trading
code, and it never claims a local JSON report is independently certified.
All returned fields are allowlisted, bounded, and advisory-ineligible.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path


MAX_REPORT_BYTES = 1024 * 1024
REPORT_NAME = "synthetic_confluence_stress.json"
SUPPORTED_SETUPS = {"TREND_CONTINUATION_V1", "BREAKOUT_RETEST_V1"}
SUPPORTED_MODELS = {"logistic_calibrated", "gradient_boosting_calibrated"}
SUPPORTED_COSTS = {"baseline_synthetic_cost", "double_friction_stress"}


def unavailable(status="NOT_CONFIGURED"):
    """Never invent a market prediction, model readiness or test results."""
    return {
        "schema_version": 1,
        "status": status,
        "source": "NONE",
        "report_modified_at_utc": None,
        "instrument": "USTECH100M",
        "model_status": "MODEL_NOT_READY",
        "real_market_inference_authorized": False,
        "real_market_training_authorized": False,
        "trade_execution_authorized": False,
        "synthetic_only": True,
        "synthetic_paths": None,
        "hypothetical_cost_scenarios": None,
        "run_count": None,
        "comparisons": [],
    }


def _reject_constant(value):
    raise ValueError("Invalid nonfinite number")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _strict_positive_int(value, maximum):
    return type(value) is int and 1 <= value <= maximum


def read_progress_snapshot(lab_root=None):
    """Read only reports/synthetic_confluence_stress.json from an explicit Lab root.

    A missing, overlarge, malformed or unsafe report yields no observations.
    No arbitrary client filename or path parameter is supported.
    """
    base = lab_root if lab_root is not None else os.environ.get("SMARTHUB_NAS100_LAB_ROOT", "")
    if not isinstance(base, (str, os.PathLike)) or not str(base).strip():
        return unavailable("NOT_CONFIGURED")
    try:
        root = Path(base).resolve(strict=True)
        report_dir = root / "reports"
        candidate = report_dir / REPORT_NAME
        if (not root.is_dir() or report_dir.is_symlink()
                or not report_dir.is_dir() or candidate.is_symlink()
                or not candidate.is_file()):
            return unavailable("NO_VALID_REPORT")
        if not candidate.resolve(strict=True).is_relative_to(root):
            return unavailable("NO_VALID_REPORT")
        stat = candidate.stat()
        if not 0 < stat.st_size <= MAX_REPORT_BYTES:
            return unavailable("INVALID_REPORT")
        raw = candidate.read_bytes()
        if len(raw) > MAX_REPORT_BYTES:
            return unavailable("INVALID_REPORT")
        source = json.loads(
            raw.decode("utf-8"), parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
        if type(source) is not dict:
            return unavailable("INVALID_REPORT")
        if (
            source.get("status") != "SYNTHETIC_PATH_AND_COST_STRESS_ONLY"
            or source.get("synthetic_only") is not True
            or source.get("real_market_training_authorized") is not False
            or source.get("real_market_inference_authorized") is not False
            or source.get("model_selection_authorized") is not False
            or source.get("profitability_claim_authorized") is not False
        ):
            return unavailable("INVALID_REPORT")
        seeds = source.get("configured_seeds")
        costs = source.get("configured_cost_scenarios")
        runs = source.get("runs")
        count = source.get("run_count")
        if (
            type(seeds) is not list or not 2 <= len(seeds) <= 6
            or any(type(v) is not int or not 0 <= v < 2**32 for v in seeds)
            or len(set(seeds)) != len(seeds)
            or costs != ["baseline_synthetic_cost", "double_friction_stress"]
            or type(runs) is not list or len(runs) != len(seeds) * len(costs)
            or not _strict_positive_int(count, 12) or count != len(runs)
        ):
            return unavailable("INVALID_REPORT")
        pairs = set()
        for run in runs:
            if type(run) is not dict:
                return unavailable("INVALID_REPORT")
            if (run.get("synthetic_only") is not True
                    or run.get("real_market_training_authorized") is not False
                    or run.get("real_market_inference_authorized") is not False
                    or run.get("model_selection_authorized") is not False
                    or run.get("profitability_claim_authorized") is not False):
                return unavailable("INVALID_REPORT")
            pair = (run.get("seed"), run.get("cost_scenario"))
            if pair in pairs or pair[0] not in seeds or pair[1] not in costs:
                return unavailable("INVALID_REPORT")
            pairs.add(pair)
        if len(pairs) != len(runs):
            return unavailable("INVALID_REPORT")

        rows = source.get("descriptive_stability_by_scenario_setup_model")
        if type(rows) is not list or len(rows) > 8:
            return unavailable("INVALID_REPORT")
        result_rows = []
        seen = set()
        for row in rows:
            if type(row) is not dict:
                return unavailable("INVALID_REPORT")
            setup = row.get("setup_id")
            model = row.get("model")
            cost = row.get("cost_scenario")
            total = row.get("seeds_with_scored_paired_results")
            positive = row.get("seeds_with_positive_confluence_delta")
            key = (setup, model, cost)
            if (
                setup not in SUPPORTED_SETUPS or model not in SUPPORTED_MODELS
                or cost not in SUPPORTED_COSTS or key in seen
                or not _strict_positive_int(total, len(seeds))
                or type(positive) is not int or not 0 <= positive <= total
                or row.get("market_edge_confirmed") is not False
                or row.get("model_selection_authorized") is not False
            ):
                return unavailable("INVALID_REPORT")
            seen.add(key)
            result_rows.append({
                "setup_id": setup,
                "model": model,
                "cost_scenario": cost,
                "improved_synthetic_paths": positive,
                "evaluated_synthetic_paths": total,
            })
        result_rows.sort(key=lambda x: (
            x["setup_id"], x["model"], x["cost_scenario"]
        ))
        return {
            "schema_version": 1,
            "status": "SYNTHETIC_REPORT_AVAILABLE",
            "source": "LOCAL_UNATTESTED_SYNTHETIC_REPORT",
            "report_modified_at_utc": datetime.fromtimestamp(
                stat.st_mtime, timezone.utc
            ).isoformat(),
            "instrument": "USTECH100M",
            "model_status": "MODEL_NOT_READY",
            "real_market_inference_authorized": False,
            "real_market_training_authorized": False,
            "trade_execution_authorized": False,
            "synthetic_only": True,
            "synthetic_paths": len(seeds),
            "hypothetical_cost_scenarios": len(costs),
            "run_count": count,
            "comparisons": result_rows,
        }
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError):
        return unavailable("INVALID_REPORT")
