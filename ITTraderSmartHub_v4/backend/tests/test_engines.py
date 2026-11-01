import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from risk_engine import calculate_risk, calculate_pipnex_lot_size, calculate_prop_firm_rules
from trade_analysis import analyze_deals

@pytest.mark.parametrize('stress,effective',[ (0,1.0),(40,0.8),(80,0.6),(100,0.5)])
def test_risk(stress,effective):
    r = calculate_risk(2000,1.0,stress)
    assert r.effective_percent == pytest.approx(effective)
    assert r.cash_limit == pytest.approx(2000*effective/100)

@pytest.mark.parametrize('balance,base,stress',[(0,1,0),(-1,1,0),(100,0,0),(100,101,0),(100,1,101),(float('nan'),1,2)])
def test_invalid_risk(balance,base,stress):
    with pytest.raises(ValueError): calculate_risk(balance,base,stress)

def test_pipnex_lot_calculator():
    # Forex EURUSD: $10,000 balance, 1% risk ($100), 20 pips stop loss -> 0.50 lots ($5/pip)
    calc = calculate_pipnex_lot_size(10000.0, 1.0, 20.0, "EURUSD")
    assert calc["recommended_lots"] == 0.50
    assert calc["cash_at_risk"] == 100.0
    assert calc["pip_value_usd"] == 5.0

    # Gold XAUUSD: $10,000 balance, 2% risk ($200), 50 pips stop loss -> 0.40 lots ($4/pip)
    gold_calc = calculate_pipnex_lot_size(10000.0, 2.0, 50.0, "XAUUSD")
    assert gold_calc["recommended_lots"] == 0.40
    assert gold_calc["cash_at_risk"] == 200.0

def test_pipnex_prop_firm_rules():
    # $100,000 balance, equity $96,000 (4% daily drawdown) -> Healthy
    pf = calculate_prop_firm_rules(96000.0, 100000.0, 100000.0)
    assert pf["daily_drawdown_pct"] == 4.0
    assert pf["is_violation"] is False

    # $100,000 balance, equity $94,500 (5.5% loss) -> Violation
    pf_fail = calculate_prop_firm_rules(94500.0, 100000.0, 100000.0)
    assert pf_fail["is_violation"] is True
    assert pf_fail["status"] == "PROP FIRM RULE VIOLATED"

def test_revenge_detection_only_after_loss_close():
    records = [
      dict(ticket=1, position_id=10, entry=0, time=1000, volume=.1, symbol='EURUSD', profit=0),
      dict(ticket=2, position_id=10, entry=1, time=1500, volume=.1, symbol='EURUSD', profit=-20),
      dict(ticket=3, position_id=11, entry=0, time=1600, volume=.1, symbol='EURUSD', profit=0)
    ]
    x = analyze_deals(records)
    assert x['revenge_count'] == 1 and x['total_entry_deals'] == 2

def test_deals_without_position_ids_not_classified():
    assert analyze_deals([dict(ticket=1, time=1000, volume=1, symbol='BTCUSD', entry=0, profit=0)])['total_entry_deals'] == 0
