"""Pipnex lot sizing must reject unverified broker contracts and never breach risk limits."""
import sys
from pathlib import Path
from dataclasses import replace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from risk_engine import BrokerContractSpec, calculate_pipnex_lot_size


@pytest.fixture
def verified_us100_spec():
    # Synthetic contract fixture ONLY: these are not actual FTMO specifications.
    return BrokerContractSpec(
        symbol="US100",
        tick_size=0.1,
        tick_value_loss_usd=0.1,
        pip_size=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        contract_size=1.0,
        account_currency="USD",
        source="TRUSTED_SERVER_SIDE_MT5",
    )


@pytest.mark.parametrize("symbol", ["US100", "USTEC", "USTECH100M", "NAS100", "EURUSD", "XAUUSD", "BTCUSD"])
def test_no_broker_spec_never_suggests_lots(symbol):
    with pytest.raises(ValueError, match="BROKER_SPEC_UNVERIFIED"):
        calculate_pipnex_lot_size(10_000.0, 1.0, 20.0, symbol)


def test_only_matching_usd_loss_tick_spec_can_size(verified_us100_spec):
    result = calculate_pipnex_lot_size(10_000.0, 1.0, 20.0, "US100", broker_spec=verified_us100_spec)
    assert result["recommended_lots"] == 5.0
    assert result["cash_at_risk"] == 100.0
    assert result["pip_value_usd"] == 5.0
    assert result["risk_budget_usd"] == 100.0
    assert result["status"] == "SIZED_FROM_VERIFIED_SPEC"
    assert result["execution_authorized"] is False


def test_min_lot_cannot_override_risk_budget(verified_us100_spec):
    spec = replace(verified_us100_spec, volume_min=0.10)
    with pytest.raises(ValueError, match="MIN_LOT_EXCEEDS_RISK_LIMIT"):
        calculate_pipnex_lot_size(100.0, 1.0, 100.0, "US100", broker_spec=spec)


def test_rounds_down_on_min_based_step_grid(verified_us100_spec):
    spec = replace(verified_us100_spec, volume_min=0.10, volume_step=0.20)
    result = calculate_pipnex_lot_size(3_500.0, 1.0, 20.0, "US100", broker_spec=spec)
    assert result["recommended_lots"] == 1.70
    assert result["cash_at_risk"] == 34.0
    assert result["cash_at_risk"] <= result["risk_budget_usd"]



def test_fractional_stop_distance_ceil_to_tradable_tick(verified_us100_spec):
    # A 0.15-price-unit requested stop with 0.1 tick must be risked as 2 ticks.
    spec = replace(verified_us100_spec, pip_size=0.15)
    result = calculate_pipnex_lot_size(1_000.0, 1.0, 1.0, "US100", broker_spec=spec)
    assert result["effective_stop_loss_ticks"] == 2
    assert result["recommended_lots"] == 50.0
    assert result["cash_at_risk"] == 10.0


def test_risk_limit_above_100_is_rejected(verified_us100_spec):
    with pytest.raises(ValueError, match="at most 100"):
        calculate_pipnex_lot_size(10_000, 105, 20, "US100", broker_spec=verified_us100_spec)


def test_respects_broker_volume_max(verified_us100_spec):
    spec = replace(verified_us100_spec, volume_max=0.40)
    result = calculate_pipnex_lot_size(10_000.0, 1.0, 20.0, "US100", broker_spec=spec)
    assert result["recommended_lots"] == 0.40
    assert result["cash_at_risk"] <= result["risk_budget_usd"]


@pytest.mark.parametrize("change", [
    {"symbol": "EURUSD"},
    {"tick_size": 0.0},
    {"tick_value_loss_usd": 0.0},
    {"tick_value_loss_usd": float("nan")},
    {"pip_size": -1.0},
    {"volume_min": 0.0},
    {"volume_max": 0.0},
    {"volume_step": 0.0},
    {"volume_max": 0.005},
    {"contract_size": float("inf")},
    {"account_currency": "EUR"},
    {"source": "USER_ENTERED"},
])
def test_unsafe_specs_fail_closed(verified_us100_spec, change):
    bad_spec = replace(verified_us100_spec, **change)
    with pytest.raises(ValueError, match="BROKER_SPEC_UNVERIFIED|INVALID_BROKER_SPEC"):
        calculate_pipnex_lot_size(10_000.0, 1.0, 20.0, "US100", broker_spec=bad_spec)


def test_rejects_untrusted_dict_instead_of_broker_object(verified_us100_spec):
    with pytest.raises(ValueError, match="BROKER_SPEC_UNVERIFIED"):
        calculate_pipnex_lot_size(10_000, 1, 20, "US100", broker_spec=vars(verified_us100_spec))


@pytest.mark.parametrize("invalid", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_stop_distance_or_budget_is_rejected(verified_us100_spec, invalid):
    with pytest.raises(ValueError):
        calculate_pipnex_lot_size(10_000, 1, invalid, "US100", broker_spec=verified_us100_spec)


def test_http_calculator_rejects_client_supplied_broker_spec(monkeypatch):
    # A phone must never be able to forge tick value/min volume through JSON.
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "s" * 48)
    from app import app
    client = app.test_client()
    response = client.post(
        "/api/v4/pipnex/calculator",
        headers={"Authorization": "Bearer " + ("s" * 48)},
        json={
            "balance": 10_000, "risk_pct": 1, "stop_loss_pips": 20,
            "symbol": "US100",
            "broker_spec": {
                "symbol": "US100", "tick_size": 0.1,
                "tick_value_loss_usd": 0.1, "volume_min": 0.01,
                "volume_step": 0.01, "volume_max": 100,
                "source": "TRUSTED_SERVER_SIDE_MT5",
            }
        },
    )
    assert response.status_code in (400, 422)
    payload = response.get_json()
    assert "BROKER_SPEC_UNVERIFIED" in payload["error"]
    assert "recommended_lots" not in payload


def test_unverified_calc_is_never_formatted_as_tradable_size(monkeypatch):
    # Legacy UI displays a 0.01-lot default for successful responses; error
    # responses must never contain 'recommended_lots'.
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "q" * 48)
    from app import app
    response = app.test_client().post(
        "/api/v4/pipnex/calculator",
        headers={"Authorization": "Bearer " + ("q" * 48)},
        json={"balance": 10000, "risk_pct": 1, "stop_loss_pips": 20, "symbol": "US100"},
    )
    assert response.status_code in (400, 422)
    assert "recommended_lots" not in response.get_json()
