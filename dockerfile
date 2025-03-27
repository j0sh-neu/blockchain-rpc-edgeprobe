FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /data

# Set environment variable
ENV DATABASE_PATH="/data/latency_tracker.db"

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "edgeprobe.py"]