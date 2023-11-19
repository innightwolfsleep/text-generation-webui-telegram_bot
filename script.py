import asyncio
import os
from threading import Thread

from dotenv import load_dotenv
from extensions.telegram_bot.main import AiogramLlmBot

# This module added to get compatibility with text-generation-webui-telegram_bot

config_file_path = "extensions/telegram_bot/configs/ext_config.json"


def run_server(token=""):
    if not token:
        load_dotenv()
        token = os.environ.get("BOT_TOKEN", "")
    # create TelegramBotWrapper instance
    # by default, read parameters in telegram_config.cfg
    tg_server = AiogramLlmBot(config_file_path=config_file_path)
    asyncio.run(tg_server.run_telegram_bot(token))


def setup():
    Thread(target=run_server, daemon=True).start()
