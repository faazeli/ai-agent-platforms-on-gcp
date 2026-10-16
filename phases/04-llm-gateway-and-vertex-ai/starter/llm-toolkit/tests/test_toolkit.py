"""Offline tests for the LLM toolkit. A scripted fake client stands in for the
gateway, so no keys or network are needed."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from costpilot_llm.evals.build_evalset import build_cases
from costpilot_llm.evals.data import build_context, load_facts
from costpilot_llm.evals.run_eval import run_cases
from costpilot_llm.evals.scorer import Answer, is_correct, summarize
from costpilot_llm.prompts import load_prompt
from costpilot_llm.spend_to_focus import FOCUS_COLUMNS, to_focus_rows
from costpilot_llm.structured import StructuredOutputError, ask_structured, strip_fences

GATEWAY_DIR = Path(__file__).resolve().parents[3] / "gateway"
GOOD = '{"answer_type": "number", "value": "12.50", "unit": "USD", "explanation": "Sum."}'


class ScriptedClient:
    """Mimics openai.AsyncOpenAI: returns the scripted replies in order and records requests."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.requests.append(kwargs)
        content = self.replies.pop(0)
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=usage)


# ------------------------------------------------------------ structured output
async def test_valid_output_parses_first_time():
    client = ScriptedClient(GOOD)
    parsed = await ask_structured(client, model="fast", schema=Answer, messages=[{"role": "user", "content": "q"}])
    assert parsed.value.value == "12.50" and parsed.attempts == 1
    sent = client.requests[0]
    assert sent["model"] == "fast"  # an alias, never a vendor model id
    assert sent["response_format"]["json_schema"]["name"] == "Answer"


async def test_invalid_output_is_repaired_with_the_errors_fed_back():
    client = ScriptedClient('{"answer_type": "number"}', GOOD)
    parsed = await ask_structured(client, model="fast", schema=Answer, messages=[{"role": "user", "content": "q"}])
    assert parsed.attempts == 2
    repair_message = client.requests[1]["messages"][-1]["content"]
    assert "value" in repair_message and "explanation" in repair_message


async def test_gives_up_with_problem_details_after_max_repairs():
    client = ScriptedClient("not json", "still not", "nope")
    with pytest.raises(StructuredOutputError) as err:
        await ask_structured(client, model="fast", schema=Answer, messages=[], max_repairs=2)
    assert err.value.problem["status"] == 502 and err.value.problem["type"].endswith("/llm-output-invalid")
    assert len(client.requests) == 3


def test_fences_are_stripped_locally():
    assert strip_fences(f"```json\n{GOOD}\n```") == GOOD
    assert strip_fences(GOOD) == GOOD


# ------------------------------------------------------------ prompts
def test_latest_prompt_is_loaded_and_rendered():
    prompt = load_prompt("cost_analyst")
    assert prompt.version >= 2 and prompt.metadata["owner"]
    text = prompt.render(context='{"x": 1}', question="How much?")
    assert "How much?" in text and '{"answer_type": "number"' in text  # literal JSON survives


def test_missing_values_are_an_error_not_a_silent_blank():
    with pytest.raises(KeyError, match="question"):
        load_prompt("cost_analyst", 1).render(context="{}")


# ------------------------------------------------------------ evals
def test_evalset_has_25_cases_with_ground_truth_from_data():
    cases = build_cases(load_facts())
    assert len(cases) == 25 and len({c["id"] for c in cases}) == 25
    anomaly = next(c for c in cases if c["tag"] == "anomaly")
    assert anomaly["expected"]["value"] == "2026-09-18"


def test_committed_evalset_matches_the_data():
    committed = Path(__file__).resolve().parents[1] / "evals" / "evalset.jsonl"
    assert [json.loads(line) for line in committed.read_text().splitlines()] == build_cases(load_facts())


def test_context_contains_every_fact_the_questions_need():
    context = json.dumps(build_context(load_facts()))
    for needle in ("untagged", "daily_usage_2026-09", "by_service", "billed"):
        assert needle in context


@pytest.mark.parametrize("expected, value, ok", [
    ({"answer_type": "number", "value": "1000.00"}, "1,003.00", True),     # 0.3% off, separators ok
    ({"answer_type": "number", "value": "1000.00"}, "1010", False),        # 1% off
    ({"answer_type": "text", "value": "BigQuery"}, " bigquery ", True),
    ({"answer_type": "date", "value": "2026-09-18"}, "2026-09-17", False),
])
def test_scoring_rules(expected, value, ok):
    assert is_correct(expected, Answer(answer_type=expected["answer_type"], value=value, explanation="")) is ok


async def test_runner_scores_a_perfect_fake_model():
    cases = build_cases(load_facts())
    truth = {c["question"]: c["expected"] for c in cases}

    async def oracle(question):
        e = truth[question]
        return Answer(answer_type=e["answer_type"], value=e["value"], unit=e["unit"], explanation="."), 1

    summary = summarize(await run_cases(cases, oracle))
    assert summary["accuracy"] == 1.0 and summary["parse_failures"] == 0


# ------------------------------------------------------------ gateway + AI spend
def test_gateway_config_uses_role_aliases_and_fallbacks():
    config = yaml.safe_load((GATEWAY_DIR / "config.yaml").read_text())
    aliases = {m["model_name"] for m in config["model_list"]}
    assert aliases == {"fast", "smart"}
    assert config["router_settings"]["fallbacks"] == [{"smart": ["fast"]}]
    assert config["general_settings"]["master_key"].startswith("os.environ/")  # no secrets in the file


def test_spend_logs_become_daily_focus_rows():
    logs = [
        {"startTime": "2026-10-01T10:00:00Z", "model_group": "fast", "spend": 0.0125,
         "metadata": {"user_api_key_metadata": {"agent": "cost-analyst", "team": "finops"}}},
        {"startTime": "2026-10-01T18:30:00Z", "model_group": "fast", "spend": 0.0075,
         "metadata": {"user_api_key_metadata": {"agent": "cost-analyst", "team": "finops"}}},
        {"startTime": "2026-10-02T09:00:00Z", "model_group": "smart", "spend": 0.2,
         "metadata": json.dumps({"user_api_key_metadata": {"agent": "recommender", "team": "finops"}})},
    ]
    rows = to_focus_rows(logs)
    assert len(rows) == 2 and set(rows[0]) == set(FOCUS_COLUMNS)
    assert rows[0]["EffectiveCost"] == "0.020000" and rows[0]["ServiceCategory"] == "AI and Machine Learning"
    assert rows[1]["ResourceId"] == "litellm/recommender/smart" and rows[1]["x_TeamId"] == "finops"
