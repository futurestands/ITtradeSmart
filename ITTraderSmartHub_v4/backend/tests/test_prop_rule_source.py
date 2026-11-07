import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import Mock
import urllib.error
import pytest

path=Path(__file__).resolve().parents[1]/'tools/check_ftmo_rule_source.py'
spec=importlib.util.spec_from_file_location('rule_source_test',path)
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

class Response:
    headers={'Content-Type':'text/html; charset=utf-8'}
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def geturl(self): return module.URL
    def read(self,limit): return b'<html>synthetic source fingerprint fixture</html>'

def prepare(monkeypatch,response=None,error=None):
    opener=Mock()
    opener.open.side_effect=error
    opener.open.return_value=response or Response()
    monkeypatch.setattr(module.urllib.request,'build_opener',lambda *args:opener)
    return opener

def test_no_baseline_never_becomes_approved_rules(monkeypatch):
    opener=prepare(monkeypatch); result=module.fingerprint()
    assert result['status']=='REVIEW_REQUIRED_NO_APPROVED_BASELINE'
    assert result['rules_verified_for_account'] is False and result['execution_authorized'] is False
    assert opener.open.call_args[0][0].full_url==module.URL

def test_unchanged_document_still_requires_purchased_account_binding(monkeypatch):
    response=Response(); prepare(monkeypatch,response)
    result=module.fingerprint(hashlib.sha256(response.read(1)).hexdigest())
    assert result['status']=='SOURCE_UNCHANGED_REVIEWED_ACCOUNT_BINDING_STILL_REQUIRED'
    assert result['decision']=='NO_TRADE'

def test_changed_document_never_auto_updates_profile(monkeypatch):
    prepare(monkeypatch); result=module.fingerprint('f'*64)
    assert result['status']=='SOURCE_CHANGED_REVIEW_REQUIRED'

def test_denied_source_does_not_return_a_fake_hash(monkeypatch):
    prepare(monkeypatch,error=urllib.error.HTTPError(module.URL,403,'private diagnostic',{},None))
    result=module.fingerprint()
    assert result['status']=='SOURCE_UNAVAILABLE_NO_NEW_PLAN' and 'content_sha256' not in result
    assert 'private diagnostic' not in str(result)

def test_redirect_handler_refuses_following_redirects():
    assert module.NoRedirects().redirect_request(None,None,302,'',{},'https://other.example') is None

def test_unexpected_final_endpoint_rejected(monkeypatch):
    response=Response(); response.geturl=lambda:'https://other.example'
    prepare(monkeypatch,response)
    assert module.fingerprint()['status']=='SOURCE_UNAVAILABLE_NO_NEW_PLAN'
