import os

# The Phase 1-2 tests exercise data behaviour, not auth, so they run in local-dev
# mode. This must be set before cost_api.main is imported, because the module-level
# `app = create_app()` fails fast when auth is on but not configured (by design).
# tests/test_auth.py builds its own apps with auth turned on.
os.environ.setdefault("COST_API_AUTH_ENABLED", "false")
