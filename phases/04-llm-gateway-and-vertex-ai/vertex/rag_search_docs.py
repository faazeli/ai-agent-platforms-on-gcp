"""Lab 4.5 (4) — ground answers in your own docs with Vertex AI RAG Engine.

Indexes your ADRs and FOCUS notes, then runs a retrieval query. Afterwards you
wrap `search_docs` as an MCP tool in Phase 3's server (see the README).

    pip install google-cloud-aiplatform
    gcloud storage cp -r docs/ gs://$BUCKET/costpilot-docs/
    PROJECT=my-project LOCATION=us-central1 DOCS=gs://$BUCKET/costpilot-docs/ \
      python vertex/rag_search_docs.py "Why did we partition the cost table by day?"

RAG Engine's API surface evolves; if a call below has moved, check the current
"RAG Engine API" page in the Vertex AI docs. The flow (corpus → import →
retrieve) stays the same. Delete the corpus when done: it bills while it exists.
"""

import os
import sys

import vertexai
from vertexai import rag

vertexai.init(project=os.environ["PROJECT"], location=os.environ.get("LOCATION", "us-central1"))

existing = [c for c in rag.list_corpora() if c.display_name == "costpilot-docs"]
corpus = existing[0] if existing else rag.create_corpus(display_name="costpilot-docs")
if not existing:
    rag.import_files(
        corpus.name,
        paths=[os.environ["DOCS"]],
        transformation_config=rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(chunk_size=512, chunk_overlap=64)),
    )
    print("imported docs into", corpus.name)

question = sys.argv[1] if len(sys.argv) > 1 else "What is EffectiveCost?"
response = rag.retrieval_query(
    rag_resources=[rag.RagResource(rag_corpus=corpus.name)],
    text=question,
    rag_retrieval_config=rag.RagRetrievalConfig(top_k=3),
)
for ctx in response.contexts.contexts:
    print(f"- {ctx.source_uri}\n  {ctx.text[:200]!r}")
print(f"\nCorpus: {corpus.name}\nDelete it when finished: rag.delete_corpus(name='{corpus.name}')")
