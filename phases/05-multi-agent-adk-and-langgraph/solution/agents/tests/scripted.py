"""A test double for an LLM: it replays a script of model turns.

Each script item is a genai Part: either a function call (the model decides to
call a tool or transfer to an agent) or text (the model answers). ADK runs the
real agent loop around it, including callbacks, tools and delegation.
"""

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types


def call(name: str, **args) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


def say(text: str) -> types.Part:
    return types.Part(text=text)


class ScriptedLlm(BaseLlm):
    script: list = []
    requests: list = []

    @classmethod
    def supported_models(cls):
        return ["scripted"]

    async def generate_content_async(self, llm_request, stream=False):
        self.requests.append(llm_request)
        part = self.script.pop(0) if self.script else say("(script exhausted)")
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def scripted(*parts: types.Part) -> ScriptedLlm:
    return ScriptedLlm(model="scripted", script=list(parts), requests=[])
