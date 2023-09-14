import sys
import os
from threading import Thread
from main import TelegramBotWrapper
from dotenv import load_dotenv

config_file_path = "configs/app_config.json"


def run_server(token):
    if not token:
        load_dotenv()
        token = os.environ.get("BOT_TOKEN", "")
    # create TelegramBotWrapper instance
    # by default, read parameters in telegram_config.cfg
    tg_server = TelegramBotWrapper(config_file_path=config_file_path)
    # by default - read token from telegram_token.txt
    tg_server.run_telegram_bot(bot_token=str(token))


def setup(token):
    Thread(target=run_server, args=(token,)).start()


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    if len(sys.argv) > 1:
        setup(sys.argv[1])
    else:
        setup("")
