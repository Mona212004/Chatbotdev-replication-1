import os
import logging

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, SimilarityFunction
from transformers import AutoTokenizer

os.environ["TOKENIZERS_PARALLELISM"] = "false"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-base-en-v1.5"
INSTRUCTION = "Represent this sentence for searching relevant passages: "
MAX_TOKENS = 512

# Loaded once at process startup (not per-request)
logger.info(f"Loading {MODEL_NAME}...")
model = SentenceTransformer(
    MODEL_NAME, similarity_fn_name=SimilarityFunction.DOT_PRODUCT
)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
logger.info("Model loaded.")

app = FastAPI(title="BGE Embedding Service")


class EmbedRequest(BaseModel):
    queries: list[str]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/embed")
async def embed(request: EmbedRequest):
    user_queries = request.queries

    if not user_queries:
        return {"error": "queries must be a non-empty list of strings."}
    if not all(isinstance(q, str) and q.strip() for q in user_queries):
        return {"error": "All queries must be non-empty strings."}

    full_queries = [INSTRUCTION + q for q in user_queries]

    for i, fq in enumerate(full_queries):
        tokens = tokenizer.encode(fq, add_special_tokens=True)
        if len(tokens) > MAX_TOKENS:
            return {
                "error": f"Query {i+1} exceeds {MAX_TOKENS} tokens (length: {len(tokens)})."
            }

    logger.info(f"Encoding {len(user_queries)} queries.")
    embeddings = model.encode(
        full_queries,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return {"embeddings": embeddings.tolist()}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
