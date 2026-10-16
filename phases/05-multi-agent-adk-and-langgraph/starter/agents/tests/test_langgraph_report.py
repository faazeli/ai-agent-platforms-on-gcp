"""The LangGraph report graph with fake node work: revision loop, human approval
pause, and resuming from a checkpoint after a "crash"."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from costpilot_agents.langgraph_report.graph import MAX_REVISIONS, ReportDeps, Review, build_report_graph


def deps(reviews: list[bool], calls: list[str]):
    verdicts = iter(reviews)

    async def gather(team_id, month):
        calls.append("gather")
        return {"total": "6079.20"}

    async def write(state):
        calls.append("write")
        return f"Draft {state.get('revisions', 0) + 1}: {state['team_id']} spent {state['facts']['total']}"

    async def review(state):
        calls.append("review")
        passed = next(verdicts)
        return Review(passed, "" if passed else "A number is not in the facts.")

    return ReportDeps(gather=gather, write=write, review=review)


CONFIG = {"configurable": {"thread_id": "t1"}}
START = {"team_id": "payments", "month": "2026-09"}


async def test_review_failure_triggers_one_rewrite_then_pauses_for_approval():
    calls = []
    graph = build_report_graph(deps([False, True], calls), InMemorySaver())
    result = await graph.ainvoke(START, CONFIG)
    assert calls == ["gather", "write", "review", "write", "review"]
    assert result["__interrupt__"][0].value["draft"].startswith("Draft 2")
    state = await graph.aget_state(CONFIG)
    assert state.next == ("approve",)  # paused, not finished


async def test_revision_loop_is_bounded():
    calls = []
    graph = build_report_graph(deps([False] * 10, calls), InMemorySaver())
    await graph.ainvoke(START, CONFIG)
    assert calls.count("write") == MAX_REVISIONS  # gives up rewriting and asks a human


async def test_human_decision_resumes_the_same_thread():
    graph = build_report_graph(deps([True], []), InMemorySaver())
    await graph.ainvoke(START, CONFIG)
    final = await graph.ainvoke(Command(resume="approved"), CONFIG)
    assert final["decision"] == "approved"


async def test_a_new_process_resumes_from_the_checkpoint_without_redoing_work():
    saver = InMemorySaver()  # in production: AsyncPostgresSaver, which survives restarts
    first_calls, second_calls = [], []
    await build_report_graph(deps([True], first_calls), saver).ainvoke(START, CONFIG)
    # "Restart": a brand-new graph object sharing only the checkpointer.
    reborn = build_report_graph(deps([], second_calls), saver)
    final = await reborn.ainvoke(Command(resume="rejected"), CONFIG)
    assert second_calls == []  # nothing re-ran: gather/write/review came from the checkpoint
    assert final["decision"] == "rejected"
