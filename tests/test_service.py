import pytest
from advisor.service import advise
from advisor.core.schemas import AdvisorResponse

def test_advise_needs_clarification():
    # If we pass a completely ambiguous query, it should return a clarification question
    resp = advise("hello", session_id="test")
    assert resp.message is not None
    assert "What kind" in resp.message
    assert resp.status == "needs_clarification"
    assert resp.recommendations == []

def test_advise_no_clarification_needed(monkeypatch):
    from advisor.core.schemas import ParsedQuery, Budget
    # If we pass a well-formed query, it should not need clarification
    # We mock Gateway.call to simulate a successful LLM extraction
    def mock_call(self, *args, **kwargs):
        print("MOCK CALLED")
        from advisor.llm.base import ProviderResponse
        return ProviderResponse(
            text="{}",
            tokens_in=10,
            tokens_out=10,
            structured_data=ParsedQuery(
                query="laptop under 50k",
                language="en",
                query_en="laptop under 50k",
                category="Electronics",
                use_case="gaming",
                budget=Budget(max_inr=50000)
            )
        )
    from advisor.llm.gateway import Gateway
    monkeypatch.setattr(Gateway, "call", mock_call)
    
    resp = advise("laptop under 50k", session_id="test")
    print("MOCK RETURNED:", resp)
    assert resp.status == "ok"
