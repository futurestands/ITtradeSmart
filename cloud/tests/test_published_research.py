"""Read-only deployment artifact, integrity and existing phone contract."""
import hashlib
import json
from pathlib import Path
import pytest
from test_auth import fixture, enrollment, auth
import published_research as published


def test_authenticated_phone_receives_only_recorded_synthetic_results(fixture):
    store, client, _, _ = fixture
    assert client.get('/api/v5/ai/research-progress').status_code == 401
    session, _ = enrollment(store, client)
    response = client.get('/api/v5/ai/research-progress', headers=auth(session))
    body = response.json
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    assert body['status'] == 'SYNTHETIC_REPORT_AVAILABLE'
    assert (body['synthetic_paths'], body['hypothetical_cost_scenarios'], body['run_count']) == (3, 2, 6)
    assert len(body['comparisons']) == 8
    assert body['report_modified_at_utc'] == published.SOURCE_MODIFIED_AT
    assert body['synthetic_only'] is True and body['model_status'] == 'MODEL_NOT_READY'
    for key in ('real_market_inference_authorized', 'real_market_training_authorized', 'trade_execution_authorized'):
        assert body[key] is False


@pytest.mark.parametrize('failure', ['missing', 'tampered', 'unsafe_with_matching_digest'])
def test_artifact_failure_never_promotes_or_serves_results(tmp_path, monkeypatch, failure):
    original = published.BUNDLE_ROOT/'reports/synthetic_confluence_stress.json'
    target = tmp_path/'reports/synthetic_confluence_stress.json'
    target.parent.mkdir()
    if failure != 'missing':
        data = original.read_bytes()
        if failure == 'tampered':
            data += b' '
        else:
            value = json.loads(data)
            value['real_market_training_authorized'] = True
            data = json.dumps(value).encode()
            monkeypatch.setattr(published, 'EXPECTED_SHA256', hashlib.sha256(data).hexdigest())
        target.write_bytes(data)
    monkeypatch.setattr(published, 'BUNDLE_ROOT', tmp_path)
    body = published.published_snapshot()
    assert body['status'] in ('NO_VALID_REPORT', 'INVALID_REPORT')
    assert body['comparisons'] == [] and body['source'] == 'NONE'
    assert body['real_market_training_authorized'] is False
