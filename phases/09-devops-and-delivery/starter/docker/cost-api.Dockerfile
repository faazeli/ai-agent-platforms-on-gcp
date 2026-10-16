# Lab 9.1 — this works, but it is not production-ready. Fix it:
#   1. multi-stage: build in one stage, copy only the virtualenv into the final image
#   2. run as a non-root user (uid 10001), no shell login
#   3. no build tools, caches or source trees in the final image
#   4. install the security library and cost-api[bigquery] (Phase 6 versions)
#   5. bake in data/sample for dev, set PYTHONUNBUFFERED, expose 8000
# Then lint with hadolint and compare image sizes before/after (docker images).
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install ./phases/06-security-and-governance/solution/security \
    ./phases/06-security-and-governance/solution/cost-api
CMD uvicorn cost_api.main:app --host 0.0.0.0 --port 8000
