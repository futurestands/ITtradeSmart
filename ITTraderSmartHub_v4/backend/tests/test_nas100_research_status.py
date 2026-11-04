"""NAS100 research-progress API: strict local read-only report, device authorization."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nas100_research_status import read_progress_snapshot, unavailable


def example_stress_report():
    seeds = [42, 1042, 2042]
    costs = ["baseline_synthetic_cost", "double_friction_stress"]
    runs = [
        {
            "seed": seed,
            "cost_scenario": cost,
            "synthetic_only": True,
            "real_market_training_authorized": False,
            "real_market_inference_authorized": False,
            "model_selection_authorized": False,
            "profitability_claim_authorized": False,
        }
        for seed in seeds for cost in costs
    ]
    return {
        "status": "SYNTHETIC_PATH_AND_COST_STRESS_ONLY",
        "synthetic_only": True,
        "real_market_training_authorized": False,
        "real_market_inference_authorized": False,
        "model_selection_authorized": False,
        "profitability_claim_authorized": False,
        "configured_seeds": seeds,
        "configured_cost_scenarios": costs,
        "run_count": 6,
        "runs": runs,
        "descriptive_stability_by_scenario_setup_model": [
            {
                "setup_id": "TREND_CONTINUATION_V1",
                "model": "logistic_calibrated",
                "cost_scenario": "baseline_synthetic_cost",
                "seeds_with_scored_paired_results": 3,
                "seeds_with_positive_confluence_delta": 3,
                "market_edge_confirmed": False,
                "model_selection_authorized": False,
            },
            {
                "setup_id": "BREAKOUT_RETEST_V1",
                "model": "gradient_boosting_calibrated",
                "cost_scenario": "double_friction_stress",
                "seeds_with_scored_paired_results": 3,
                "seeds_with_positive_confluence_delta": 2,
                "market_edge_confirmed": False,
                "model_selection_authorized": False,
            },
        ],
    }


def write_report(tmp_path, payload=None):
    lab = tmp_path / "lab"
    report_dir = lab / "reports"
    report_dir.mkdir(parents=True)
    report = report_dir / "synthetic_confluence_stress.json"
    report.write_text(json.dumps(
        example_stress_report() if payload is None else payload
    ), encoding="utf-8")
    return lab, report


def test_no_config_and_missing_report_always_unavailable(tmp_path):
    assert read_progress_snapshot("")["status"] == "NOT_CONFIGURED"
    root = tmp_path / "newlab"
    root.mkdir()
    assert read_progress_snapshot(root)["status"] == "NO_VALID_REPORT"
    assert read_progress_snapshot(root)["real_market_inference_authorized"] is False


def test_real_synthetic_report_generates_only_bounded_status_fields(tmp_path):
    root, _ = write_report(tmp_path)
    result = read_progress_snapshot(root)
    assert result["status"] == "SYNTHETIC_REPORT_AVAILABLE"
    assert result["synthetic_paths"] == 3
    assert result["run_count"] == 6
    assert result["hypothetical_cost_scenarios"] == 2
    assert len(result["comparisons"]) == 2
    assert result["comparisons"][0]["setup_id"] == "BREAKOUT_RETEST_V1"
    assert result["comparisons"][1]["improved_synthetic_paths"] == 3
    assert result["source"] == "LOCAL_UNATTESTED_SYNTHETIC_REPORT"
    assert result["model_status"] == "MODEL_NOT_READY"
    assert result["real_market_training_authorized"] is False
    assert result["trade_execution_authorized"] is False
    assert "probability" not in json.dumps(result)
    assert "entry_price" not in json.dumps(result)
    assert "file_path" not in json.dumps(result)


@pytest.mark.parametrize("field,value", [
    ("synthetic_only", False),
    ("real_market_training_authorized", True),
    ("real_market_inference_authorized", True),
    ("model_selection_authorized", True),
    ("profitability_claim_authorized", True),
    ("status", "REAL_APPROVED"),
])
def test_refuse_fake_readiness_or_genuine_market_claims(tmp_path, field, value):
    data = example_stress_report()
    data[field] = value
    root, _ = write_report(tmp_path, data)
    assert read_progress_snapshot(root)["status"] == "INVALID_REPORT"


def test_missing_per_run_safety_field_fails_closed(tmp_path):
    data = example_stress_report()
    del data["runs"][0]["synthetic_only"]
    root, _ = write_report(tmp_path, data)
    assert read_progress_snapshot(root)["status"] == "INVALID_REPORT"


def test_duplicate_or_unrecognized_model_scores_rejected(tmp_path):
    data = example_stress_report()
    data["descriptive_stability_by_scenario_setup_model"][0]["model"] = "UNAPPROVED_LIVE_MODEL"
    root, _ = write_report(tmp_path, data)
    assert read_progress_snapshot(root)["status"] == "INVALID_REPORT"


def test_duplicate_json_keys_rejected(tmp_path):
    root, path = write_report(tmp_path)
    path.write_bytes(b'{"status":"x","status":"SYNTHETIC_PATH_AND_COST_STRESS_ONLY"}')
    assert read_progress_snapshot(root)["status"] == "INVALID_REPORT"


@pytest.mark.parametrize("raw", [
    b'{"status":NaN}', b"{}", b"[]", b"\xff\xfe", b"x" * (1024 * 1024 + 1),
])
def test_malformed_nonfinite_and_oversized_documents_fail_closed(tmp_path, raw):
    root, path = write_report(tmp_path)
    path.write_bytes(raw)
    assert read_progress_snapshot(root)["status"] == "INVALID_REPORT"


def test_path_is_fixed_and_symlink_is_rejected(tmp_path):
    root, path = write_report(tmp_path)
    if not hasattr(os, "symlink"):
        pytest.skip("Symbolic links unsupported")
    backup = path.with_name("synthetic-other.json")
    path.rename(backup)
    try:
        path.symlink_to(backup)
    except OSError:
        pytest.skip("Insufficient filesystem symlink privileges")
    assert read_progress_snapshot(root)["status"] == "NO_VALID_REPORT"


def test_gateway_route_requires_enrolled_device_and_changes_no_bot_mode(monkeypatch, tmp_path):
    root, _ = write_report(tmp_path)
    monkeypatch.setenv("SMARTHUB_NAS100_LAB_ROOT", str(root))
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    import app as gateway
    from v4_services import ContextStore
    from bot import BotController

    monkeypatch.setattr(gateway, "_v4_store", ContextStore())
    monkeypatch.setattr(gateway, "_bot", BotController())
    gateway.app.config["TESTING"] = True
    client = gateway.app.test_client()
    assert client.get("/api/v5/ai/research-progress").status_code == 401
    code = gateway._v4_store.generate_pairing_code()["pairing_code"]
    token = gateway._v4_store.enroll_device("nas100-read-only-test", "TEST", code)["device_token"]
    headers = {"Authorization": "Bearer " + token}
    state_before = gateway._bot.get_status()
    resp = client.get("/api/v5/ai/research-progress", headers=headers)
    assert resp.status_code == 200
    assert resp.json["status"] == "SYNTHETIC_REPORT_AVAILABLE"
    assert resp.json["real_market_inference_authorized"] is False
    assert "no-store" in resp.headers["Cache-Control"]
    assert gateway._bot.get_status() == state_before
    # Device cannot change privileged bot operation through this route.
    assert client.post("/api/v5/bot/mode", headers=headers, json={"mode": "PAPER"}).status_code == 403
