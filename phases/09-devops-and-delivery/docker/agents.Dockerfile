# syntax=docker/dockerfile:1.7
# CostPilot agents (Phase 5) served by ADK's API server. Build from the repo root:
#   docker build -f phases/09-devops-and-delivery/docker/agents.Dockerfile -t agents:dev .

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /src
COPY phases/04-llm-gateway-and-vertex-ai/solution/llm-toolkit ./llm-toolkit
COPY phases/06-security-and-governance/solution/security ./security
COPY phases/05-multi-agent-adk-and-langgraph/solution/agents ./agents
RUN uv venv /app/.venv \
 && VIRTUAL_ENV=/app/.venv uv pip install --no-cache ./llm-toolkit "./security[adk]" ./agents

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY phases/05-multi-agent-adk-and-langgraph/solution/agents/adk_apps /app/adk_apps
# The eval set travels with the image so a canary can be judged in-cluster (Lab 9.5)
COPY phases/04-llm-gateway-and-vertex-ai/solution/llm-toolkit/evals/evalset.jsonl /app/evals/evalset.jsonl
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8080
CMD ["adk", "api_server", "--host", "0.0.0.0", "--port", "8080", "/app/adk_apps"]
