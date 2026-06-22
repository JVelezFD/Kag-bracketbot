# BracketBot — Dockerfile for Cloud Run

FROM python:3.11-slim

WORKDIR /app

# Copy and install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run sets PORT automatically — default to 8080
ENV PORT=8080
ENV ENVIRONMENT=production

EXPOSE 8080

CMD ["python", "main.py"]
