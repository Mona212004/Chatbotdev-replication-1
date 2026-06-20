# 1. Use an official, lightweight Python runtime as a parent image
FROM python:3.11-slim

# 2. Prevent Python from writing .pyc files to disk and ensure logs print immediately
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Install system dependencies required for compiled modules (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copy the requirements file first to take advantage of Docker layer caching
COPY requirements.txt .

# 6. Install the Python packages smoothly without using local cache storage
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 7. Copy the rest of the embedding service code into the container
COPY . .

# 8. Expose the port Uvicorn will listen on (Render will dynamically override this via $PORT)
EXPOSE 10000

# 9. Run the application using the standard exec form
CMD ["python", "app.py"]