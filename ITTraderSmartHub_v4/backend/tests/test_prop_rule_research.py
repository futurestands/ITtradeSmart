from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock
import pytest
import ssl
import prop_rule_research as module

NOW = datetime(2026,11,11,tzinfo=timezone.utc)


def context():
    return module.AccountRuleContext('private-test-ref','FTMO','2-Step','Phase 1','USD',Decimal('10000'),'fixture-terms-v1')


def review(active=None, reviewed=None, **kwargs):
    args=dict(source_id='ftmo_objectives',approved_hash='a'*64,current_hash='a'*64,checked_at=NOW,now=NOW)
    args.update(kwargs)
    return module.review_source_binding(active or context(),reviewed or context(),**args)


@pytest.mark.parametrize('field,value', [('account_ref','other'),('firm','FUNDEDNEXT'),('programme','1-Step'),
    ('stage','Funded'),('currency','EUR'),('original_size',Decimal('100000')),('terms_version','v2')])
def test_switching_any_account_context_invalidates_old_review(field,value):
    result=review(active=replace(context(),**{field:value}))
    assert 'ACCOUNT_CONTEXT_CHANGED_REVIEW_REQUIRED' in result['blockers']
    assert result['execution_authorized'] is False and result['decision']=='NO_TRADE'


def test_unchanged_source_never_approves_policy():
    result=review()
    assert result['status']=='SOURCE_UNCHANGED_ACCOUNT_TERMS_REVIEW_STILL_REQUIRED'
    assert not result['rules_verified_for_account'] and not result['execution_authorized']


@pytest.mark.parametrize('args,reason', [({'current_hash':'b'*64},'SOURCE_CHANGED_REVIEW_REQUIRED'),
    ({'current_hash':None},'SOURCE_EVIDENCE_MISSING'),
    ({'source_id':'fundednext_help'},'SOURCE_FIRM_MISMATCH_OR_UNSUPPORTED'),
    ({'checked_at':NOW-timedelta(days=2)},'STALE_FUTURE_OR_INVALID_SOURCE_CHECK'),
    ({'checked_at':NOW+timedelta(seconds=1)},'STALE_FUTURE_OR_INVALID_SOURCE_CHECK'),
    ({'max_age_seconds':86401},'STALE_FUTURE_OR_INVALID_SOURCE_CHECK')])
def test_research_gates_fail_closed(args,reason):
    assert reason in review(**args)['blockers']


@pytest.mark.parametrize('value',[Decimal('0'),Decimal('NaN'),10000,'10000',True])
def test_no_size_guess_or_nonfinite_size(value):
    with pytest.raises(ValueError):replace(context(),original_size=value)


def test_arbitrary_urls_are_not_fetchable():
    with pytest.raises(ValueError):module.fingerprint_source('http://127.0.0.1/private')
    assert module.NoRedirects().redirect_request(None,None,302,'',{},'https://other.example') is None


def test_fetch_never_sends_private_context_or_approves_rules(monkeypatch):
    response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
    response.geturl.return_value=module.SOURCES['ftmo_objectives'][1]
    response.headers={'Content-Type':'text/html'};response.read.return_value=b'<html>fixture</html>'
    opener=Mock();opener.open.return_value=response
    def build(*args):
        https = next(a for a in args if isinstance(a, module.urllib.request.HTTPSHandler))
        assert https._context.check_hostname is True
        assert https._context.verify_mode == ssl.CERT_REQUIRED
        return opener
    monkeypatch.setattr(module.urllib.request,'build_opener',build)
    result=module.fingerprint_source('ftmo_objectives')
    request=opener.open.call_args[0][0]
    assert request.data is None and request.full_url==module.SOURCES['ftmo_objectives'][1]
    assert 'private-test-ref' not in str(request.headers)
    assert result['tls_certificate_verification'] is True and not result['rules_verified_for_account']


def test_unavailable_source_never_supplies_fake_hash(monkeypatch):
    opener=Mock();opener.open.side_effect=RuntimeError('private error detail')
    monkeypatch.setattr(module.urllib.request,'build_opener',lambda *args:opener)
    result=module.fingerprint_source('ftmo_objectives')
    assert result['status']=='SOURCE_UNAVAILABLE_NO_NEW_PLAN' and 'content_sha256' not in result
    assert 'private error detail' not in str(result)
