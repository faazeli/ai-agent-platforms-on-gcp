"""Lab 3.5 bonus — generate MCP tools straight from cost-api's FastAPI app.

Run from this phase's folder, with the Phase 1 solution installed or on PYTHONPATH:
    PYTHONPATH=../01-fastapi-pydantic-problem-details/solution/cost-api/src \
      python bonus/generated_from_openapi.py

It prints the tools FastMCP generates. Compare them with the hand-written tools in
solution/mcp-finops: look at the names, the descriptions a model would read, and
the input bounds. Then write an ADR: generated, hand-written, or a mix?
"""

import asyncio

from fastmcp import Client, FastMCP

from cost_api.main import create_app


async def main() -> None:
    generated = FastMCP.from_fastapi(app=create_app(), name="cost-api-generated")
    async with Client(generated) as client:
        for tool in await client.list_tools():
            print(f"- {tool.name}\n    {(tool.description or '').splitlines()[0] if tool.description else '(no description)'}")


if __name__ == "__main__":
    asyncio.run(main())
