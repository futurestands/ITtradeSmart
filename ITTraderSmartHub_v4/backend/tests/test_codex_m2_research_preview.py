"""Authenticated offline prototype: no data inputs, broker, estimator or orders."""
import pytest
from test_analyze_api import api, ADMIN

URL = '/api/v5/nas100/research-preview'


def test_preview_requires_authentication(api, monkeypatch):
    client, fake, _ = api
    monkeypatch.setenv('SMARTHUB_SYNTHETIC_PREVIEW_ENABLED', '1')
    assert client.get(URL).status_code == 401
    assert fake.calls == []


def test_preview_default_off(api, monkeypatch):
    client, fake, _ = api
    monkeypatch.delenv('SMARTHUB_SYNTHETIC_PREVIEW_ENABLED', raising=False)
    assert client.get(URL, headers=ADMIN).status_code == 503
    assert fake.calls == []


def test_preview_exposes_rule_engine_without_predictive_claims(api, monkeypatch):
    client, fake, _ = api
    monkeypatch.setenv('SMARTHUB_SYNTHETIC_PREVIEW_ENABLED', '1')
    response = client.get(URL, headers=ADMIN)
    assert response.status_code == 200
    body = response.get_json()
    assert body['decision'] == 'NO_TRADE'
    assert body['probability'] is None and body['model_status'] == 'MODEL_NOT_READY'
    assert body['data']['is_synthetic'] is True
    assert body['data']['freshness'] == 'FIXED_OFFLINE_FIXTURE_NOT_LIVE'
    assert body['data']['research_eligible'] is False
    assert body['analysis']['bars'] == 96
    assert body['reasons'] and body['invalidation']
    assert response.headers['Cache-Control'] == 'no-store'
    assert client.get(URL, headers=ADMIN).get_json() == body
    assert fake.calls == []


@pytest.mark.parametrize('query', ['path=private.csv', 'symbol=USTECH100M', 'prices=1', 'count=200000'])
def test_preview_rejects_all_client_data_inputs(api, monkeypatch, query):
    client, fake, _ = api
    monkeypatch.setenv('SMARTHUB_SYNTHETIC_PREVIEW_ENABLED', '1')
    assert client.get(URL+'?'+query, headers=ADMIN).status_code == 400
    assert fake.calls == []


def test_enrolled_device_can_read_but_cannot_change_bot_state(api, monkeypatch):
    client, fake, gateway = api
    monkeypatch.setenv('SMARTHUB_SYNTHETIC_PREVIEW_ENABLED', '1')
    code = gateway._v4_store.generate_pairing_code()['pairing_code']
    token = gateway._v4_store.enroll_device('synthetic-preview-test', 'TEST', code)['device_token']
    headers = {'Authorization': 'Bearer '+token}
    before = gateway._bot.get_status()
    assert client.get(URL, headers=headers).status_code == 200
    assert gateway._bot.get_status() == before
    assert client.post('/api/v5/bot/mode', headers=headers, json={'mode': 'PAPER'}).status_code == 403
    assert fake.calls == []


def test_preview_rejects_request_body(api, monkeypatch):
    client, fake, _ = api
    monkeypatch.setenv('SMARTHUB_SYNTHETIC_PREVIEW_ENABLED', '1')
    assert client.get(URL, data='client-provided-prices', headers=ADMIN).status_code == 400
    assert fake.calls == []
