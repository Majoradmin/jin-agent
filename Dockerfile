FROM python:3.11-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project code
COPY jin_agent/ ./jin_agent/

# Data folder (config will be set via environment variables)
RUN mkdir -p /app/jin_agent/data/reports /app/jin_agent/data/backups

# Startup: run Telegram bot
CMD ["python", "-m", "jin_agent", "bot"]
