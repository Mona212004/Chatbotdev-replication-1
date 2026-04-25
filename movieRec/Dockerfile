FROM python:3.12-slim  

WORKDIR /app

# Copy requirements from the subfolder (path relative to build context root)
COPY movieRecommendation/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["adk", "web", ".", "--host", "0.0.0.0"]