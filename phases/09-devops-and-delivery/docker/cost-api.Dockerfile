# syntax=docker/dockerfile:1.7
# cost-api (Phase 6 secured version). Build from the REPO ROOT:
#   docker build -f phases/09-devops-and-delivery/docker/cost-api.Dockerfile -t cost-api:dev .
#
# Multi-stage: build tools stay in the first stage; the final image has only the
# virtualenv and runs as a non-root user. Pin the base image by digest in your
# own repo (Renovate keeps digests current), e.g. python:3.12-slim@sha256:...

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
WORKDIR /src
COPY phases/06-security-and-governance/solution/security ./security
COPY phases/06-security-and-governance/solution/cost-api ./cost-api
RUN uv venv /app/.venv \
 && VIRTUAL_ENV=/app/.venv uv pip install --no-cache ./security "./cost-api[bigquery]"

FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# Sample data for COST_API_DATA_SOURCE=memory (dev only; prod reads BigQuery)
COPY data/sample /app/data/sample
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COST_API_SAMPLE_CSV=/app/data/sample/focus_costs.csv
USER 10001
EXPOSE 8000
CMD ["uvicorn", "cost_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
