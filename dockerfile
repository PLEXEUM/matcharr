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

# Create cron script
RUN echo "#!/bin/bash" > /run-cron.sh
RUN echo "echo 'Running Matcharr at $(date)' >> /var/log/matcharr.log" >> /run-cron.sh
RUN echo "cd /app && python app.py >> /var/log/matcharr.log 2>&1" >> /run-cron.sh
RUN echo "echo 'Matcharr completed at $(date)' >> /var/log/matcharr.log" >> /run-cron.sh
RUN chmod +x /run-cron.sh

# Setup cron
RUN echo "SHELL=/bin/bash" > /etc/cron.d/matcharr
RUN echo "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" >> /etc/cron.d/matcharr
RUN echo "$CRON_SCHEDULE root /run-cron.sh" >> /etc/cron.d/matcharr

# Create log file
RUN touch /var/log/matcharr.log

# Print startup message to Docker logs
RUN echo "echo 'Matcharr container started. Waiting for cron schedule...'" > /startup.sh
RUN echo "echo 'Cron schedule: $CRON_SCHEDULE'" >> /startup.sh
RUN echo "echo 'Logs will appear in /var/log/matcharr.log'" >> /startup.sh
RUN echo "cron -f" >> /startup.sh
RUN chmod +x /startup.sh

CMD ["/startup.sh"]