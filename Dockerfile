FROM python:3.11-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project code
COPY jin_agent/ ./jin_agent/
# bot.py bhi — kuch hosts (FadeHost) default start command 'python bot.py' chalate hain
COPY bot.py ./

# Data folder (config will be set via environment variables).
# VOLUME: DB/reports/backups container rebuild ke baad bhi barqarar rahein.
# 0700: multi-user host par dusre users archive/backup na parhein.
RUN mkdir -p -m 0700 /app/jin_agent/data/reports /app/jin_agent/data/backups \
    && chmod 0700 /app/jin_agent/data
VOLUME /app/jin_agent/data

# Console port. Hosted platforms (FadeHost/Render/Railway) ko JIN_AGENT_HOST=0.0.0.0
# env set karna hota hai; code ka default hamesha loopback (127.0.0.1) rehta hai.
EXPOSE 8766

# Supervisor: Agent Console (HTTP /api/health) + Telegram bot (long polling)
# ek saath, auto-restart ke saath. Bot akele port nahi kholta -> 502 hota tha.
CMD ["python", "-m", "jin_agent", "supervisor"]
