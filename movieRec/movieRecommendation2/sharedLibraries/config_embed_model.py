import os

# URL of the standalone embedding service (set this env var on the chatbot's Render service)
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:10000")
