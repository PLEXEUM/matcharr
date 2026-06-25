FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (cron is NOT needed - Python handles scheduling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py ./
COPY config.json.sample ./config.json

# Create logs directory
RUN mkdir -p /app/logs

# Set default cron schedule if not provided
ENV CRON_SCHEDULE="0 2 * * *"

# Run app.py directly - it handles scheduling internally via croniter
CMD ["python", "app.py"]