"""Model Armor guardrails: screen prompts before the model and responses after it.

Model Armor is a Google Cloud service that screens text against a *template* of
filters: prompt injection and jailbreak, sensitive data (via Sensitive Data
Protection), malicious URLs, and responsible-AI categories. This client calls its
REST API directly (one POST per check) so you can see exactly what happens:

  POST https://modelarmor.{location}.rep.googleapis.com/v1/projects/{project}/
       locations/{location}/templates/{template}:sanitizeUserPrompt
       {"userPromptData": {"text": "..."}}
  → {"sanitizationResult": {"filterMatchState": "MATCH_FOUND" | "NO_MATCH_FOUND",
                            "filterResults": {...}}}

``adk_callbacks`` plugs it into Phase 5's agents. It screens the newest content
before each model call: a user message, or a tool result, which is where
*indirect* prompt injection arrives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

TokenProvider = Callable[[], Awaitable[str]]


@dataclass
class Verdict:
    blocked: bool
    matched_filters: list[str] = field(default_factory=list)
    error: str | None = None


def _matched(filter_results: dict[str, Any]) -> list[str]:
    """Collect the top-level filter names whose nested result says MATCH_FOUND."""
    found = []
    for name, result in (filter_results or {}).items():
        if '"MATCH_FOUND"' in json.dumps(result):
            found.append(name)
    return sorted(found)


class ModelArmorClient:
    def __init__(self, *, project: str, location: str, template: str, token: TokenProvider,
                 http: httpx.AsyncClient | None = None, fail_closed: bool = True) -> None:
        self._base = (f"https://modelarmor.{location}.rep.googleapis.com/v1/projects/{project}"
                      f"/locations/{location}/templates/{template}")
        self._token, self._http = token, http or httpx.AsyncClient(timeout=5.0)
        # fail_closed: if Model Armor is unreachable, block. Choose deliberately and write it down.
        self.fail_closed = fail_closed

    async def _sanitize(self, method: str, body: dict[str, Any]) -> Verdict:
        try:
            response = await self._http.post(f"{self._base}:{method}", json=body,
                                             headers={"Authorization": f"Bearer {await self._token()}"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return Verdict(blocked=self.fail_closed, error=type(exc).__name__)
        result = response.json().get("sanitizationResult", {})
        blocked = result.get("filterMatchState") == "MATCH_FOUND"
        return Verdict(blocked=blocked, matched_filters=_matched(result.get("filterResults", {})))

    async def check_prompt(self, text: str) -> Verdict:
        return await self._sanitize("sanitizeUserPrompt", {"userPromptData": {"text": text}})

    async def check_response(self, text: str) -> Verdict:
        return await self._sanitize("sanitizeModelResponse", {"modelResponseData": {"text": text}})


def google_token_provider() -> TokenProvider:
    """Access tokens from Application Default Credentials (Workload Identity on GKE)."""
    import asyncio

    import google.auth
    import google.auth.transport.requests

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

    async def token() -> str:
        if not credentials.valid:
            await asyncio.to_thread(credentials.refresh, google.auth.transport.requests.Request())
        return credentials.token

    return token


def _newest_text(llm_request: Any) -> str:
    """What to screen before a model call: the latest user message plus every tool
    result since the model last spoke. Agent hand-offs (transfer_to_agent) are
    plumbing, not content, so they are skipped rather than screened instead of the
    user's words."""
    tool_results: list[str] = []
    user_text = ""
    for content in reversed(llm_request.contents or []):
        for part in content.parts or []:
            response = part.function_response
            if response is not None and response.name != "transfer_to_agent" and not user_text:
                tool_results.append(json.dumps(response.response, default=str))
            elif part.text and content.role == "user" and not user_text:
                user_text = part.text
        if user_text:
            break
    return "\n".join([user_text, *reversed(tool_results)]).strip()


def adk_callbacks(client: ModelArmorClient, audit: Callable[[dict[str, Any]], None] | None = None):
    """Returns (before_model_callback, after_model_callback) for an ADK LlmAgent."""
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    def refusal(text: str) -> LlmResponse:
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))

    async def before_model(callback_context, llm_request):
        verdict = await client.check_prompt(_newest_text(llm_request))
        if audit:
            audit({"event": "guardrail_prompt", "decision": "blocked" if verdict.blocked else "allowed",
                   "filters": verdict.matched_filters, "error": verdict.error})
        if verdict.blocked:
            return refusal("I can't continue with that request: it was flagged by a safety check.")
        return None

    async def after_model(callback_context, llm_response):
        parts = (llm_response.content.parts if llm_response.content else None) or []
        text = "\n".join(p.text for p in parts if p.text)
        if not text:
            return None  # function calls are checked by the tool guard instead
        verdict = await client.check_response(text)
        if audit:
            audit({"event": "guardrail_response", "decision": "blocked" if verdict.blocked else "allowed",
                   "filters": verdict.matched_filters, "error": verdict.error})
        return refusal("I generated a response that failed a safety check, so I withheld it.") \
            if verdict.blocked else None

    return before_model, after_model
