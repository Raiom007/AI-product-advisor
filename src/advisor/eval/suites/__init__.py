from advisor.core.registries import suite
from advisor.eval.suites.guardrails import guardrails_suite
from advisor.eval.suites.parser import parser_suite

# TODO: Split into one-file-per-suite (per ARCHITECTURE.md §3) once fakes/vision/guardrails suites get real logic.

def _check_data(data: list):
    if not data:
        raise ValueError("FAIL LOUDLY: no data")

@suite("retrieval")
def retrieval_suite(data: list, mode: str):
    _check_data(data)
    # Stub

@suite("baseline_compare")
def baseline_compare_suite(data: list, mode: str):
    _check_data(data)
    # Stub

@suite("fakes")
def fakes_suite(data: list, mode: str):
    _check_data(data)
    # Stub

@suite("vision")
def vision_suite(data: list, mode: str):
    _check_data(data)
    # Stub




@suite("e2e")
def e2e_suite(data: list, mode: str):
    _check_data(data)
    # e2e suite calls service.advise()
    from advisor.service import advise
    for query in data:
        resp = advise(query, session_id="eval")
    # Return canned metrics or whatever
    return {"status": "ok"}
