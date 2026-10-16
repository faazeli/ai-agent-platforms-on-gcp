# syntax=docker/dockerfile:1.7
# mcp-finops (Phase 6 secured version). Build from the repo root:
#   docker build -f phases/09-devops-and-delivery/docker/mcp-finops.Dockerfile -t mcp-finops:dev .

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /src
COPY phases/06-security-and-governance/solution/security ./security
COPY phases/06-security-and-governance/solution/mcp-finops ./mcp-finops
RUN uv venv /app/.venv \
 && VIRTUAL_ENV=/app/.venv uv pip install --no-cache ./security ./mcp-finops

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8001
CMD ["python", "-m", "mcp_finops"]
