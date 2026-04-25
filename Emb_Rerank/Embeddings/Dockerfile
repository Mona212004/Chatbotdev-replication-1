# 1. Base Image: Use a stable official Python image as the starting point.
FROM python:3.11-slim

# 2. Set Working Directory: Define the directory where the app code will live inside the container.
WORKDIR /app

# 3. Copy Dependencies: Copy the requirements file first to take advantage of Docker's caching.
COPY requirements.txt .

# 4. Install Dependencies: Install all necessary Python packages.
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Source Code: Copy all other files from your project root into the container's /app directory.
COPY . .

# 6. Command to Run: Define the default command to execute when the container starts.
# Replace 'main.py' with the actual entry point of your application.
CMD ["python", "createVectorDB/main.py"]