import pytest

import advisor.eval.suites  # noqa: F401
from advisor.core.registries import eval_suites

@pytest.mark.parametrize("suite_name", [
    "retrieval",
    "baseline_compare",
    "fakes",
    "vision",
    "guardrails",
    "parser",
    "e2e"
])
def test_suites_fail_loudly_on_no_data(suite_name):
    runner = eval_suites.get(suite_name)
    assert runner is not None, f"Suite {suite_name} not registered"

    with pytest.raises(ValueError, match="FAIL LOUDLY: no data"):
        runner(data=[], mode="replay")
