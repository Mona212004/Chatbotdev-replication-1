# convert a list of user queries to vector embedding
import requests
import numpy as np
import os
import logging

from movieRec.movieRecommendation2.sharedLibraries.config_embed_model import (
    EMBEDDING_SERVICE_URL,
)

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

    logger.info(f"Sending {len(user_queries)} queries to embedding service.")
    try:
        response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json={"queries": user_queries},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            logger.error(f"Embedding service returned an error: {data['error']}")
            raise ValueError(data["error"])

        q_embeddings = np.array(data["embeddings"])

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
    except requests.RequestException as error:
        logger.error(f"Embedding service request failed: {str(error)}", exc_info=True)
        raise RuntimeError(f"Embedding service request failed: {str(error)}") from error
    except Exception as error:
        logger.error(f"Embedding generation failed: {str(error)}", exc_info=True)
        raise RuntimeError(f"Embedding generation failed: {str(error)}") from error


if __name__ == "__main__":
    result = query_to_vectors(["Hello", "Give me a movie", "What genres do we have?"])
    print(f"Shape: {result.shape}")
    print(result)
