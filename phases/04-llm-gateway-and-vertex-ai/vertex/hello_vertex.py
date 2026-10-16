"""Lab 4.1 — call Gemini on Vertex AI directly, with a typed response.

    pip install google-genai pydantic
    gcloud auth application-default login
    PROJECT=my-project LOCATION=global MODEL=gemini-3.5-flash python vertex/hello_vertex.py

Notice: no API key. The SDK uses Application Default Credentials locally and
Workload Identity on GKE. Check current model ids in the Vertex AI model list.
"""

import os
import time

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class CostInsight(BaseModel):
    headline: str = Field(description="One sentence")
    biggest_driver: str
    suggested_action: str


client = genai.Client(vertexai=True, project=os.environ["PROJECT"], location=os.environ.get("LOCATION", "global"))
started = time.perf_counter()
response = client.models.generate_content(
    model=os.environ.get("MODEL", "gemini-3.5-flash"),
    contents=(
        "Team payments spent 6,079 USD in September: Compute Engine 2,400, Cloud Run 1,900, "
        "BigQuery 1,300, Cloud Storage 479. Its committed-use discount was 88% utilized. "
        "Give one insight."
    ),
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CostInsight,
        temperature=0,
    ),
)
elapsed = time.perf_counter() - started

insight = CostInsight.model_validate_json(response.text)  # validate even though the API constrained it
print(insight.model_dump_json(indent=2))
usage = response.usage_metadata
print(f"latency {elapsed:.2f}s · input tokens {usage.prompt_token_count} · output tokens {usage.candidates_token_count}")
