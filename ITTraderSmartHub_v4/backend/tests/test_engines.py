import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from risk_engine import calculate_risk
from trade_analysis import analyze_deals

@pytest.mark.parametrize('stress,effective',[ (0,1.0),(40,0.8),(80,0.6),(100,0.5)])
def test_risk(stress,effective):
    r=calculate_risk(2000,1.0,stress)
    assert r.effective_percent == pytest.approx(effective)
    assert r.cash_limit == pytest.approx(2000*effective/100)

@pytest.mark.parametrize('balance,base,stress',[(0,1,0),(-1,1,0),(100,0,0),(100,101,0),(100,1,101),(float('nan'),1,2)])
def test_invalid_risk(balance,base,stress):
    with pytest.raises(ValueError):calculate_risk(balance,base,stress)

def test_revenge_detection_only_after_loss_close():
    records=[
      dict(ticket=1,position_id=10,entry=0,time=1000,volume=.1,symbol='EURUSD',profit=0),
      dict(ticket=2,position_id=10,entry=1,time=1500,volume=.1,symbol='EURUSD',profit=-20),
      dict(ticket=3,position_id=11,entry=0,time=1600,volume=.1,symbol='EURUSD',profit=0)]
    x=analyze_deals(records)
    assert x['revenge_count']==1 and x['total_entry_deals']==2

def test_deals_without_position_ids_not_classified():
    assert analyze_deals([dict(ticket=1,time=1000,volume=1,symbol='BTCUSD',entry=0,profit=0)])['total_entry_deals']==0
