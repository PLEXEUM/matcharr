FROM python:3.8-slim

WORKDIR /app

# Install system dependencies and cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files (only root Python files now)
COPY *.py ./
COPY config.json ./

# Create logs directory
RUN mkdir -p /app/logs

# Create startup script with proper line endings
RUN printf '#!/bin/bash\n' > /startup.sh && \
    printf 'echo "Matcharr container started. Waiting for cron schedule..."\n' >> /startup.sh && \
    printf 'echo "Cron schedule: $CRON_SCHEDULE"\n' >> /startup.sh && \
    printf 'echo "Logs will appear in /app/logs/matcharr.log"\n' >> /startup.sh && \
    printf 'cron -f\n' >> /startup.sh && \
    chmod +x /startup.sh

# Create cron script
RUN printf '#!/bin/bash\n' > /run-cron.sh && \
    printf 'echo "$(date) - Running Matcharr" >> /app/logs/matcharr.log\n' >> /run-cron.sh && \
    printf 'cd /app && python app.py >> /app/logs/matcharr.log 2>&1\n' >> /run-cron.sh && \
    printf 'echo "$(date) - Matcharr completed" >> /app/logs/matcharr.log\n' >> /run-cron.sh && \
    chmod +x /run-cron.sh

# Setup cron
RUN printf 'SHELL=/bin/bash\n' > /etc/cron.d/matcharr && \
    printf 'PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n' >> /etc/cron.d/matcharr && \
    printf '%s root /run-cron.sh\n' "$CRON_SCHEDULE" >> /etc/cron.d/matcharr && \
    chmod 0644 /etc/cron.d/matcharr

# Create empty log file in the mounted volume location
RUN touch /app/logs/matcharr.log

# Set default cron schedule if not provided
ENV CRON_SCHEDULE="0 2 * * *"

CMD ["/startup.sh"]