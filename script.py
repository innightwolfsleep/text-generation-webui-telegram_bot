import os
from threading import Thread
from extensions.telegram_bot.main import TelegramBotWrapper
from dotenv import load_dotenv

# This module added to get compatibility with text-generation-webui-telegram_bot

config_file_path = "extensions/telegram_bot/configs/ext_config.json"


def run_server(token=""):
    if not token:
        load_dotenv()
        token = os.environ.get("BOT_TOKEN", "")
    # create TelegramBotWrapper instance
    # by default, read parameters in telegram_config.cfg
    tg_server = TelegramBotWrapper(config_file_path=config_file_path)
    # by default - read token from extensions/telegram_bot/telegram_token.txt
    tg_server.run_telegram_bot()


def setup():
    Thread(target=run_server, daemon=True).start()
