import os
import sys
from threading import Thread

from dotenv import load_dotenv

from main import TelegramBotWrapper

default_config_file_path = "configs/app_config.json"


def run_server(token, config_file_path=""):
    if not config_file_path:
        config_file_path = default_config_file_path
    if not token:
        load_dotenv()
        token = os.environ.get("BOT_TOKEN", "")
    # create TelegramBotWrapper instance
    # by default, read parameters in telegram_config.cfg
    tg_server = TelegramBotWrapper(config_file_path=config_file_path)
    # by default - read token from telegram_token.txt
    tg_server.run_telegram_bot(bot_token=str(token))


def setup(token, config_file_path=""):
    Thread(target=run_server, args=(token, config_file_path)).start()


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    if len(sys.argv) > 2:
        setup(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        setup(sys.argv[1])
    else:
        setup("")
