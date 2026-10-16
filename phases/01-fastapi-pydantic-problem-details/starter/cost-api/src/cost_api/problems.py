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

    # TODO Lab 1.4 (a): handle RequestValidationError -> 422 "invalid-request".
    #   Add an `invalid_params` list with one {"name", "in", "reason"} per error.
    #   exc.errors() gives you dicts with "loc" (e.g. ("query", "month")) and "msg".

    # TODO Lab 1.4 (b): handle StarletteHTTPException (unknown routes, wrong
    #   methods) -> slug "not-found" for 404, "method-not-allowed" for 405.

    # TODO Lab 1.4 (c): handle any other Exception -> 500 "internal-error".
    #   Generate trace_id = uuid.uuid4().hex, log the exception with it, and
    #   return the trace_id as an extension member. Never put exc text in detail.
