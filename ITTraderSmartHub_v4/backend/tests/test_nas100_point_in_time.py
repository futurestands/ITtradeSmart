from datetime import datetime,timedelta,timezone
import pytest
from nas100.point_in_time import ContextSample,context_asof

BASE=datetime(2025,1,2,12,tzinfo=timezone.utc)
def sample(value=1.0,observed=BASE,available=BASE,verified=True,source='synthetic-test'):
    return ContextSample('context',value,'test-units',observed,available,source,verified)
def select(samples,at=BASE,age=timedelta(days=2)):
    return context_asof('context',at,samples,max_age=age)

def test_future_publication_is_not_backfilled():
    late=sample(available=BASE+timedelta(hours=2))
    assert select([late]).reason=='NOT_YET_AVAILABLE'
    assert select([late],BASE+timedelta(hours=2)).value==1

def test_future_suffix_cannot_change_historical_feature():
    known=[sample()]
    future=sample(999,BASE+timedelta(days=1),BASE+timedelta(days=1))
    assert select(known)==select(known+[future])

def test_revision_only_available_from_its_publication():
    original=sample(1)
    revision=sample(2,available=BASE+timedelta(hours=1))
    assert select([original,revision]).value==1
    assert select([original,revision],BASE+timedelta(hours=1)).value==2

def test_old_revision_does_not_replace_newer_observation():
    newer=sample(2,BASE+timedelta(hours=1),BASE+timedelta(hours=1))
    old_revision=sample(99,available=BASE+timedelta(hours=2))
    assert select([newer,old_revision],BASE+timedelta(hours=2)).value==2

def test_stale_observation_is_not_freshened_by_revision():
    old=sample(observed=BASE-timedelta(days=10),available=BASE)
    assert select([old]).reason=='STALE_CONTEXT'

def test_reference_without_verified_numeric_feed_is_excluded():
    assert select([sample(verified=False)]).reason=='UNVERIFIED_CONTEXT'
    assert select([sample(verified=False)]).value is None

def test_missing_feature_has_no_score():
    assert select([]).reason=='MISSING_CONTEXT'

@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,'1'])
def test_non_numeric_or_nonfinite_rejected(value):
    with pytest.raises(ValueError): sample(value)

def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError): sample(observed=BASE.replace(tzinfo=None))

def test_publication_before_observation_rejected():
    with pytest.raises(ValueError): sample(available=BASE-timedelta(seconds=1))

def test_conflicting_sources_fail_closed():
    with pytest.raises(ValueError): select([sample(1),sample(2,source='other-test')])

def test_equivalent_timezone_instants_align():
    alternate=sample(available=BASE.astimezone(timezone(timedelta(hours=3))))
    assert select([alternate]).available_at==BASE

def test_age_boundary_is_inclusive():
    assert select([sample()],BASE+timedelta(days=2)).reason=='AVAILABLE'
    assert select([sample()],BASE+timedelta(days=2,seconds=1)).reason=='STALE_CONTEXT'

def test_negative_age_rejected():
    with pytest.raises(ValueError): select([],age=timedelta(seconds=-1))
