"""Run the LangGraph report with a durable checkpoint and a human approval pause.

    # a Postgres for checkpoints (any will do; this one is throwaway)
    docker run -d --name lg-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 postgres:16-alpine
    export CHECKPOINT_DB=postgresql://postgres:pg@localhost:5433/postgres

    python -m costpilot_agents.langgraph_report.run start  --team payments --month 2026-09 --thread t1
    python -m costpilot_agents.langgraph_report.run resume --thread t1 --decision approved

Kill the process during `start` (Ctrl-C after "gather" prints) and run `start`
again with the same thread: it continues from the last checkpoint instead of
starting over. Without CHECKPOINT_DB an in-memory saver is used, which cannot
survive a restart, which is exactly what the exercise demonstrates.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .graph import build_report_graph
from .live import build_live_deps


@asynccontextmanager
async def checkpointer():
    url = os.environ.get("CHECKPOINT_DB")
    if not url:
        yield InMemorySaver()
        return
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(url) as saver:
        await saver.setup()  # creates tables on first use
        yield saver


async def main(args: argparse.Namespace) -> None:
    config = {"configurable": {"thread_id": args.thread}}
    async with checkpointer() as saver:
        graph = build_report_graph(await build_live_deps(), saver)
        if args.command == "start":
            existing = await graph.aget_state(config)
            payload = None if existing.next else {"team_id": args.team, "month": args.month}
            stream = graph.astream(payload, config, stream_mode="updates")
        else:
            stream = graph.astream(Command(resume=args.decision), config, stream_mode="updates")
        async for update in stream:
            for node, value in update.items():
                if node == "__interrupt__":
                    print("\n=== Waiting for approval ===\n" + value[0].value["draft"])
                    print(f"\nResume with: --thread {args.thread} resume --decision approved|rejected")
                else:
                    print(f"[{node}] done")
        final = await graph.aget_state(config)
        if not final.next:
            print("decision:", final.values.get("decision"))


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["start", "resume"])
    parser.add_argument("--thread", required=True)
    parser.add_argument("--team", default="payments")
    parser.add_argument("--month", default="2026-09")
    parser.add_argument("--decision", choices=["approved", "rejected"], default="approved")
    asyncio.run(main(parser.parse_args()))


if __name__ == "__main__":
    cli()
