"""RFC 9457 Problem Details for every error cost-api returns.

RFC 9457 obsoletes RFC 7807; the JSON shape is the same. Every error response:

* has media type ``application/problem+json``
* carries ``type``, ``title``, ``status``, ``detail``, ``instance``
* may carry extension members such as ``trace_id`` or ``invalid_params``

The ``type`` URIs are documented in ../../errors.md. Treat that catalog as part
of the API contract: clients branch on ``type``, never on ``detail`` text.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"
log = logging.getLogger("cost_api.problems")


class ProblemError(Exception):
    """Raise this anywhere in the app to return a Problem Details response."""

    def __init__(self, status: int, slug: str, title: str, detail: str, **extensions: Any) -> None:
        super().__init__(detail)
        self.status = status
        self.slug = slug
        self.title = title
        self.detail = detail
        self.extensions = extensions


def problem_body(
    base_url: str, status: int, slug: str, title: str, detail: str, instance: str, **extensions: Any
) -> dict[str, Any]:
    return {
        "type": f"{base_url.rstrip('/')}/{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
        **extensions,
    }


def _response(body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(body, status_code=body["status"], media_type=PROBLEM_JSON)


def install_problem_handlers(app: FastAPI, base_url: str) -> None:
    """Register handlers so that *every* error leaves the app as Problem Details."""

    @app.exception_handler(ProblemError)
    async def handle_problem(request: Request, exc: ProblemError) -> JSONResponse:
        return _response(problem_body(base_url, exc.status, exc.slug, exc.title, exc.detail,
                                      request.url.path, **exc.extensions))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        invalid_params = [
            {"name": ".".join(str(p) for p in err["loc"] if p not in ("query", "path", "body")),
             "in": str(err["loc"][0]) if err["loc"] else "unknown",
             "reason": err["msg"]}
            for err in exc.errors()
        ]
        return _response(problem_body(
            base_url, 422, "invalid-request", "Your request parameters didn't validate",
            f"{len(invalid_params)} parameter(s) failed validation", request.url.path,
            invalid_params=invalid_params,
        ))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Covers framework errors such as unknown routes (404) and wrong methods (405).
        slug = {404: "not-found", 405: "method-not-allowed"}.get(exc.status_code, "http-error")
        title = {404: "Resource not found", 405: "Method not allowed"}.get(exc.status_code, "HTTP error")
        return _response(problem_body(base_url, exc.status_code, slug, title, str(exc.detail), request.url.path))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Never leak stack traces or SQL. Log them with a trace id the client can quote.
        trace_id = uuid.uuid4().hex
        log.exception("unhandled error trace_id=%s", trace_id)
        return _response(problem_body(
            base_url, 500, "internal-error", "Internal server error",
            "An unexpected error occurred. Quote the trace_id when reporting it.",
            request.url.path, trace_id=trace_id,
        ))
