"""The agent eval harness, end to end with a scripted model and Phase 4's scorer."""

from scripted import call, say, scripted
from test_adk_team import tools_for

from costpilot_agents.adk.team import build_team
from costpilot_agents.evals import evaluate, trajectory_ok


def test_trajectory_rules():
    assert trajectory_ok("total", ["list_teams", "get_team_cost"])
    assert not trajectory_ok("anomaly", ["get_team_cost"])
    assert trajectory_ok("untagged", [])  # needs no tool: the honest answer is "unknown"


async def test_evaluate_scores_answer_and_path():
    from costpilot_llm.evals.scorer import Answer

    case = {"id": "q1", "tag": "total", "question": "How much did payments spend in 2026-09?",
            "expected": {"answer_type": "number", "value": "6079.20", "unit": "USD"}}
    model = scripted(call("transfer_to_agent", agent_name="cost_analyst"),
                     call("get_team_cost", team_id="payments", month="2026-09"),
                     say("Payments spent 6,079.20 USD."))
    team = build_team({n: model for n in ("coordinator", "cost_analyst", "anomaly_detector", "recommender")},
                      tools_for)

    async def extract(text):  # the live harness uses ask_structured through the gateway
        return Answer(answer_type="number", value=text.split()[2], unit="USD", explanation=text)

    report = await evaluate(team, [case], extract)
    assert report["accuracy"] == 1.0 and report["trajectory_accuracy"] == 1.0
    assert report["rows"][0]["agents"][:2] == ["coordinator", "cost_analyst"]
