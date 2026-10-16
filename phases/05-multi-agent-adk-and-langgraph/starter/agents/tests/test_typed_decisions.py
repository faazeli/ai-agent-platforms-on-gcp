"""Lab 5.9: typed decisions. Offline: the real TypeSafe SDK talks to a fake System One server."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from costpilot_agents import tickets
from costpilot_agents.typed_decisions.calibration import brier, expected_calibration_error, selective
from costpilot_agents.typed_decisions.deciders import JevDecider, LlmDecider, MockDecider, with_deadline
from costpilot_agents.typed_decisions.graph import build_triage_graph
from costpilot_agents.typed_decisions.models import CATEGORIES, URGENCY_LEVELS, AnomalyCase, Triage
from costpilot_agents.typed_decisions.policy import TriagePolicy, route
from costpilot_agents.typed_decisions.run_eval import evaluate, load_cases

CASES = load_cases()
BY_ID = {c["case"]["case_id"]: c for c in CASES}


# ------------------------------------------------------------ fake System One


def fake_system_one(answer_for, seen: list | None = None):
    """An httpx2 transport that behaves like POST /v1/systemone.

    ``answer_for(state)`` returns (p_real, category_probabilities, urgency_probabilities)."""
    httpx2 = pytest.importorskip("httpx2")

    def handler(request):
        assert request.method == "POST" and request.url.path == "/v1/systemone"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        if seen is not None:
            seen.append(body)
        p_real, cats, levels = answer_for(body["state"])
        choice = max(cats, key=cats.get)
        expected = sum(level * p for level, p in levels.items())
        return httpx2.Response(200, json={
            "model": body["model"] or "jev-latest",
            "usage": {"input_tokens": 400, "output_tokens": 3},
            "answers": {
                "real": {"type": "noul", "noul": p_real},
                "category": {"type": "choice", "choice": choice, "confidence": cats[choice], "probabilities": cats},
                "urgency": {"type": "score", "score": expected, "confidence": max(levels.values()),
                            "legend": {str(i): text for i, text in enumerate(URGENCY_LEVELS)},
                            "probabilities": {str(k): v for k, v in levels.items()}},
            },
        })

    return httpx2.MockTransport(handler)


def jev(answer_for, seen=None) -> JevDecider:
    sdk = pytest.importorskip("typesafe_sdk")
    client = sdk.AsyncTypeSafeClient(api_key="test-key", model="jev-latest", transport=fake_system_one(answer_for, seen),
                                     compression=False, retry=sdk.RetryPolicy(max_retries=0))
    return JevDecider(client)


def oracle(sharpness: float):
    """A decider that knows the labels, with probabilities as sharp as you ask (0.5 = coin flip)."""
    def answer_for(state):
        case = next(c for c in CASES if c["case"]["team_id"] == state["team_id"] and c["case"]["day"] == state["day"])
        e = case["expected"]
        p_real = sharpness if e["real"] else 1 - sharpness
        rest = (1 - sharpness) / (len(CATEGORIES) - 1)
        cats = {c: sharpness if c == e["category"] else rest for c in CATEGORIES}
        levels = {i: 0.9 if i == e["urgency"] else 0.1 / 3 for i in range(4)}
        return p_real, cats, levels
    return answer_for


# -------------------------------------------------------------------- tests


async def test_jev_request_and_answer_round_trip_through_the_sdk():
    seen: list = []
    decider = jev(oracle(0.93), seen)
    case = AnomalyCase.model_validate(BY_ID["t01"]["case"])
    triage = await decider.decide(case)

    body = seen[0]
    assert body["model"] == "jev-latest"
    assert body["state"]["team_id"] == "ml-research" and "case_id" not in body["state"]
    questions = body["questions"]
    assert {q: questions[q]["type"] for q in questions} == {"real": "noul", "category": "choice", "urgency": "score"}
    assert set(questions["category"]["criteria"]) == set(CATEGORIES)
    assert questions["urgency"]["criteria"] == URGENCY_LEVELS

    assert triage.p_real == pytest.approx(0.93)
    assert triage.category == "usage_spike" and triage.category_confidence == pytest.approx(0.93)
    assert triage.urgency_level == 2 and set(triage.urgency_probabilities) == {0, 1, 2, 3}
    assert triage.decider == "jev:jev-latest" and triage.input_tokens == 400


async def test_a_sharp_calibrated_decider_automates_more_than_the_mock():
    mock = await evaluate(MockDecider(), CASES)
    sharp = await evaluate(jev(oracle(0.95)), CASES)
    assert sharp["brier"] < mock["brier"]
    assert sharp["auto_decided"]["coverage"] > mock["auto_decided"]["coverage"]
    assert sharp["missed_real_problems"] == [] and sharp["false_alarm_proposals"] == []
    assert sharp["routes"]["review"] < mock["routes"]["review"]


async def test_an_unsure_decider_defers_to_people():
    report = await evaluate(jev(oracle(0.6)), CASES)
    assert report["routes"]["review"] == report["cases"]       # nothing automated, nothing dismissed
    assert report["routes"]["propose_ticket"] == 0


async def test_late_or_failing_decisions_become_reviews():
    class Slow:
        name = "slow"

        async def decide(self, case):
            await asyncio.sleep(1)

    class Broken:
        name = "broken"

        async def decide(self, case):
            raise RuntimeError("503")

    case = AnomalyCase.model_validate(BY_ID["t05"]["case"])
    for inner in (Slow(), Broken()):
        triage = await with_deadline(inner, 0.05).decide(case)
        assert route(triage, TriagePolicy()).kind == "review", triage.notes


def _triage(p_real, conf=0.9, urgency=1.0):
    return Triage(p_real=p_real, category="usage_spike", category_confidence=conf, category_probabilities={},
                  urgency=urgency, urgency_probabilities={}, decider="test")


def test_policy_thresholds_and_budget():
    policy = TriagePolicy()
    assert route(_triage(0.05), policy).kind == "dismiss"
    assert route(_triage(0.5), policy).kind == "review"
    assert route(_triage(0.95, conf=0.4), policy).kind == "review"     # real, but cause unclear
    proposal = route(_triage(0.95, urgency=2.8), policy)
    assert proposal.kind == "propose_ticket" and proposal.page
    capped = route(_triage(0.95), policy, proposals_today=policy.max_proposals_per_day)
    assert capped.kind == "notify" and "proposal_budget_exhausted" in capped.flags


def _graph(decider, log):
    return build_triage_graph(decider, TriagePolicy(), InMemorySaver(), log=log.append)


async def test_graph_proposes_and_only_a_person_creates_the_ticket():
    log: list = []
    graph = _graph(jev(oracle(0.95)), log)
    cfg = {"configurable": {"thread_id": "t05"}}
    before = len(tickets.CREATED)
    paused = await graph.ainvoke({"case": BY_ID["t05"]["case"]}, cfg)
    ask = paused["__interrupt__"][0].value
    assert ask["ticket"]["team_id"] == "payments" and ask["page"] is True
    assert len(tickets.CREATED) == before and not log          # nothing happens while waiting

    done = await graph.ainvoke(Command(resume="approved"), cfg)
    assert done["ticket"]["ticket_id"].startswith("FIN-") and len(tickets.CREATED) == before + 1
    assert log[0]["route"] == "propose_ticket" and log[0]["human"]["real"] is True


async def test_graph_rejection_is_logged_as_a_label():
    log: list = []
    graph = _graph(jev(oracle(0.95)), log)
    cfg = {"configurable": {"thread_id": "t13"}}
    await graph.ainvoke({"case": BY_ID["t13"]["case"]}, cfg)
    done = await graph.ainvoke(Command(resume="rejected"), cfg)
    assert done["ticket"] is None and log[0]["human"] == {"real": False, "category": None, "create_ticket": False}


async def test_graph_review_and_dismiss_paths():
    log: list = []
    graph = _graph(jev(oracle(0.95)), log)
    dismissed = await graph.ainvoke({"case": BY_ID["t03"]["case"]}, {"configurable": {"thread_id": "t03"}})
    assert "__interrupt__" not in dismissed and log[-1]["route"] == "dismiss"

    unsure = _graph(MockDecider(), log)
    cfg = {"configurable": {"thread_id": "t02"}}
    paused = await unsure.ainvoke({"case": BY_ID["t02"]["case"]}, cfg)
    assert "unsure" in paused["__interrupt__"][0].value["reason"]
    await unsure.ainvoke(Command(resume={"real": True, "category": "untagged_spend", "create_ticket": False}), cfg)
    assert log[-1]["route"] == "review" and log[-1]["human"]["category"] == "untagged_spend"


async def test_llm_decider_uses_the_phase4_repair_loop():
    replies = iter([
        '{"real": true, "real_confidence": 1.4, "category": "usage_spike", "category_confidence": 0.9, "urgency": 3}',
        '```json\n{"real": true, "real_confidence": 0.9, "category": "usage_spike", "category_confidence": 0.9, "urgency": 3}\n```',
    ])

    async def create(**kwargs):
        assert kwargs["response_format"]["type"] == "json_schema"
        usage = SimpleNamespace(prompt_tokens=300, completion_tokens=40)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(replies)))], usage=usage)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    triage = await LlmDecider(client).decide(AnomalyCase.model_validate(BY_ID["t05"]["case"]))
    assert triage.p_real == pytest.approx(0.9) and triage.urgency_level == 3
    assert "attempts=2" in triage.notes and triage.input_tokens == 600


def test_calibration_metrics():
    assert brier([1.0, 0.0], [True, False]) == 0
    assert brier([0.5] * 4, [True, False, True, False]) == pytest.approx(0.25)
    # Says 90% but is right half the time: badly calibrated.
    assert expected_calibration_error([0.9] * 4, [True, False, True, False]) == pytest.approx(0.4)
    assert selective([0.05, 0.5, 0.95], [False, True, True], 0.15, 0.85) == {"coverage": 0.667, "accuracy": 1.0}


def test_evalset_is_well_formed():
    assert len(CASES) >= 15 and len(BY_ID) == len(CASES)
    for item in CASES:
        AnomalyCase.model_validate(item["case"])
        e = item["expected"]
        assert e["category"] in CATEGORIES and 0 <= e["urgency"] <= 3 and item["why"]
        assert e["real"] or e["urgency"] == 0
    assert {c["expected"]["real"] for c in CASES} == {True, False}
