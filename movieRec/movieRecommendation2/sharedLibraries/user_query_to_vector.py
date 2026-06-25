# convert a list of user queries to vector embedding
from movieRec.movieRecommendation2.sharedLibraries.config_embed_model import model
from movieRec.movieRecommendation2.sharedLibraries.device import get_device
from transformers import AutoTokenizer
import numpy as np
import os
import logging

# Configure logging to write to console (and/or a file if desired)
# Set the desired level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
logging.basicConfig(
    level=logging.INFO,
    filename="test_user_queries.log",
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress tokenizers parallelism warning (set before any imports/usage)
os.environ["TOKENIZERS_PARALLELISM"] = "false"


# make each user query within the list stay within 512 tokens
def query_to_vectors(user_queries):
    # ensure user_query is not empty string
    if not isinstance(user_queries, list) or not user_queries:
        logger.error(
            "User queries input failed validation: Not a non-empty list of strings."
        )
        raise ValueError("user_queries must be a non-empty list of strings.")
    if not all(isinstance(q, str) and q.strip() for q in user_queries):
        logger.error(
            "User queries input failed validation: Contains non-string or empty elements."
        )
        raise ValueError("All user_queries must be non-empty strings.")

    # token check
    tokenizer_name = "BAAI/bge-base-en-v1.5"
    try:
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
    except Exception as e:
        logger.error(f"Failed to load tokenizer {tokenizer_name}: {e}")
        raise

    max_tokens = 512
    instruction = "Represent this sentence for searching relevant passages: "

    logger.info(
        f"Starting token length check for {len(user_queries)} queries (Max: {max_tokens} tokens)."
    )

    for i, q in enumerate(user_queries):
        full_query = instruction + q
        tokens = tokenizer.encode(full_query, add_special_tokens=True)
        if len(tokens) > max_tokens:
            error_msg = f"Query {i+1} exceeds {max_tokens} tokens (length: {len(tokens)}). Query: '{q[:50]}...'"
            logger.error(error_msg)
            raise ValueError(error_msg)

    devices = get_device()
    logger.info(f"Using device(s): {devices}")
    try:
        full_queries = [instruction + q for q in user_queries]
        # Use direct encode on CPU — start_multi_process_pool forks processes that
        # share model weights via /dev/shm, which hits Docker's 64MB shm cap.
        # Direct encode uses heap memory and is equally fast on a single CPU instance.
        use_pool = len(devices) > 1 or (len(devices) == 1 and devices[0] != "cpu")
        pool = None
        if use_pool:
            logger.info("Starting multi-process pool for parallel encoding.")
            pool = model.start_multi_process_pool(devices)
            logger.info(
                f"Encoding {len(user_queries)} queries with pool, batch size 32."
            )
            q_embeddings = model.encode(
                full_queries,
                pool=pool,
                batch_size=32,
                chunk_size=512,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        else:
            logger.info(f"Encoding {len(user_queries)} queries directly on CPU.")
            q_embeddings = model.encode(
                full_queries,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        # validate embeddings
        if (
            q_embeddings is None
            or len(q_embeddings) == 0
            or np.any(np.isnan(q_embeddings))
        ):
            logger.error(
                "Embedding generation produced invalid results (None, empty, or NaN values)."
            )
            raise RuntimeError("Embedding generation produced invalid results.")
        logger.info(
            f"Successfully generated vector embeddings for {len(user_queries)} user queries."
        )
        logger.info(f"Shape of generated query embeddings: {q_embeddings.shape}.")
        return q_embeddings
    except Exception as error:
        logger.error(f"Embedding generation failed: {str(error)}", exc_info=True)
        raise RuntimeError(f"Embedding generation failed: {str(error)}") from error
    finally:
        if pool is not None:
            # stop the pool (cleanup)
            logger.info("Stopping multi-process pool.")
            model.stop_multi_process_pool(pool)


if __name__ == "__main__":
    result = query_to_vectors(["Hello", "Give me a movie", "What genres do we have?"])
    print(f"Shape: {result.shape}")
    print(result)
