"""Security errors as RFC 9457 Problem Details, consistent with Phase 1.

401 responses also carry ``WWW-Authenticate: Bearer`` as RFC 6750 requires.
Details stay generic on purpose: tell the caller *what* failed, never *why* in a
way that helps someone probe your verifier.
"""

from __future__ import annotations

from typing import Any


class SecurityProblem(Exception):
    def __init__(self, status: int, slug: str, title: str, detail: str, **extensions: Any) -> None:
        super().__init__(detail)
        self.status, self.slug, self.title, self.detail, self.extensions = status, slug, title, detail, extensions

    def body(self, base_url: str, instance: str) -> dict[str, Any]:
        return {"type": f"{base_url.rstrip('/')}/{self.slug}", "title": self.title, "status": self.status,
                "detail": self.detail, "instance": instance, **self.extensions}

    @property
    def headers(self) -> dict[str, str]:
        return {"WWW-Authenticate": 'Bearer realm="costpilot"'} if self.status == 401 else {}


def install_security_handlers(app: Any, base_url: str) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(SecurityProblem)
    async def handle(request: Request, exc: SecurityProblem) -> JSONResponse:
        return JSONResponse(exc.body(base_url, request.url.path), status_code=exc.status,
                            media_type="application/problem+json", headers=exc.headers)
