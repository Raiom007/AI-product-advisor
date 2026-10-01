import pytest
from pydantic import BaseModel

from advisor.core.budget import RequestBudget
from advisor.llm.gateway import Gateway


class DummySchema(BaseModel):
    dummy_val: str = "ok"

@pytest.fixture
def fake_gateway():
    models_config = {
        "roles": {
            "test_role": {
                "candidates": [
                    {"provider": "fake", "model": "fake-1", "params": {}},
                    {"provider": "fake", "model": "fake-2", "params": {}},
                    {"provider": "fake", "model": "fake-3", "params": {}}
                ]
            }
        }
    }
    gw = Gateway(models_config, limits_config={})
    return gw

def test_retry_on_429(fake_gateway, monkeypatch):
    import advisor.llm.gateway as gateway_module
    monkeypatch.setattr(gateway_module.time, "sleep", lambda x: None)

    provider = fake_gateway.providers["fake"]
    provider.call_count = 0

    orig_complete = provider.complete
    attempt = [0]
    def mock_complete(*args, **kwargs):
        attempt[0] += 1
        if attempt[0] == 1:
            raise Exception("429 Too Many Requests")
        return orig_complete(*args, **kwargs)

    provider.complete = mock_complete

    resp = fake_gateway.call("test_role", "hello")
    # provider.call_count will only be 1 because the first attempt never reaches _check_triggers
    assert provider.call_count == 1
    assert attempt[0] == 2
    assert resp.tokens_out == 10

def test_fallback_on_5xx(fake_gateway, monkeypatch):
    import advisor.llm.gateway as gateway_module
    monkeypatch.setattr(gateway_module.time, "sleep", lambda x: None)

    provider = fake_gateway.providers["fake"]

    # It will try fake-1 (fails 3 times due to max retries), then fall back to fake-2 (which we will let succeed)
    # The prompt contains TRIGGER_5XX, but we only want fake-1 to fail? No, if prompt has TRIGGER_5XX, fake-2 fails too.
    # So we'll patch the provider to fail only if model == "fake-1"
    orig_complete = provider.complete
    def mock_complete(model, *args, **kwargs):
        if model == "fake-1":
            raise Exception("500 Internal Server Error")
        return orig_complete(model, *args, **kwargs)

    provider.complete = mock_complete

    resp = fake_gateway.call("test_role", "hello")
    # Should succeed by falling back to fake-2
    assert "fake response" in resp.text.lower()

def test_cache_hit_and_miss(fake_gateway):
    provider = fake_gateway.providers["fake"]
    provider.call_count = 0

    # 1. Call for fake-1
    resp1 = fake_gateway.call("test_role", "prompt A")
    assert provider.call_count == 1

    # 2. Call again with exact same params
    resp2 = fake_gateway.call("test_role", "prompt A")
    assert provider.call_count == 1 # Cache hit, no new calls

    # 3. Call with different prompt -> cache miss
    resp3 = fake_gateway.call("test_role", "prompt B")
    assert provider.call_count == 2

    # 4. Prove model is in key: we'll artificially modify the config so "fake-2" is first
    fake_gateway.models_config["roles"]["test_role"]["candidates"].reverse()
    resp4 = fake_gateway.call("test_role", "prompt A")
    # Even though "prompt A" for "test_role" is cached for fake-1, fake-2 is now the target, so it misses.
    assert provider.call_count == 3

def test_budget_exhaustion(fake_gateway):
    budget = RequestBudget(max_model_calls=1, max_wall_s=10)

    # First call consumes budget
    fake_gateway.call("test_role", "hello", budget=budget)

    # Second call should raise BudgetExceeded
    with pytest.raises(Exception):
        fake_gateway.call("test_role", "hello 2", budget=budget)

def test_malformed_json_repair_retry(fake_gateway):
    provider = fake_gateway.providers["fake"]
    provider.trigger_malformed = True
    provider.call_count = 0

    # call -> fails -> adds "Fix it" to prompt -> triggers again.
    # In fake.py, if "Fix it" in prompt, we unset trigger_malformed and let it pass!
    resp = fake_gateway.call("test_role", "TRIGGER_MALFORMED", schema=DummySchema)

    # call_count should be 2: original call + 1 repair retry
    assert provider.call_count == 2
    assert resp.structured_data is not None
