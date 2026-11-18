"""FadeHost / generic-hosting entry point: ``python bot.py``.

FadeHost ka default start command ``python bot.py`` hota hai. Yeh shim wahi
kaam karta hai jo ``python -m jin_agent bot`` karta hai - taake panel ke
default par bhi bot sahi se chalu ho.

Config sirf environment variables se aaata hai (repo me config.json nahi):
    TELEGRAM_BOT_TOKEN   Telegram bot token (@BotFather)
    TELEGRAM_CHAT_ID     aap ka private chat id
    GROQ_API_KEY         free-tier Groq key
    LLM_ENDPOINT         https://api.groq.com/openai/v1
    LLM_MODEL            llama-3.3-70b-versatile
    LLM_PROVIDER         groq
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jin_agent.__main__ import main  # noqa: E402  (path insert ke baad)

if __name__ == "__main__":
    raise SystemExit(main(["bot"]))
