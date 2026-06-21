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

# Copy application files
COPY *.py ./
COPY classes/ ./classes/
COPY utils/ ./utils/

# Create cron job file
RUN echo "SHELL=/bin/bash" > /etc/cron.d/matcharr
RUN echo "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" >> /etc/cron.d/matcharr
RUN echo "$CRON_SCHEDULE root cd /app && python app.py >> /var/log/matcharr.log 2>&1" >> /etc/cron.d/matcharr

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/matcharr

# Apply cron job - FIXED: use root user
RUN crontab -u root /etc/cron.d/matcharr

# Create log file
RUN touch /var/log/matcharr.log

# Run cron in foreground
CMD ["cron", "-f"]