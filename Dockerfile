FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY edgeprobe.py .
COPY config.yaml .

# Create directories for persistent volumes
RUN mkdir -p /data

# Set environment variable for database location
ENV DATABASE_PATH="/data/latency_tracker.db"

# Expose the application port
EXPOSE 8000

# Run the application
CMD ["python", "edgeprobe.py"]