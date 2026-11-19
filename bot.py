"""FadeHost / generic-hosting entry point: ``python bot.py``.

FadeHost ka default start command ``python bot.py`` hota hai. Yeh shim ab
**supervisor** chalata hai: Agent Console (HTTP port + /api/health) aur
Telegram bot (long polling) dono ek saath, auto-restart ke saath. Is se hosted
reverse proxy ko 502 nahi milta aur bot bhi chalta rehta hai.

Sirf bot chahiye (local/testing) to: ``python -m jin_agent bot``.

Config sirf environment variables se aaata hai (repo me config.json nahi):
    TELEGRAM_BOT_TOKEN   Telegram bot token (@BotFather)
    TELEGRAM_CHAT_ID     aap ka private chat id
    JIN_AGENT_HOST       console bind host — default loopback; hosted par 0.0.0.0
    PORT                 console port — default 8766
    JIN_AGENT_UPDATE_WORKERS   per-update thread pool (default 2)
    GROQ_API_KEY         free-tier Groq key
    LLM_ENDPOINT         https://api.groq.com/openai/v1
    LLM_MODEL            llama-3.3-70b-versatile
    LLM_PROVIDER         custom
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jin_agent.__main__ import main  # noqa: E402  (path insert ke baad)

if __name__ == "__main__":
    # FadeHost bina arguments ke chalata hai -> supervisor (console + bot).
    raise SystemExit(main(sys.argv[1:] or ["supervisor"]))
