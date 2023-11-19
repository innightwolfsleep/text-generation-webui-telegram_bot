import os
import sys
import asyncio

from dotenv import load_dotenv

from main import AiogramLlmBot

default_config_file_path = "configs/app_config.json"


def run_server(token, config_file_path=""):
    if not config_file_path:
        config_file_path = default_config_file_path
    if not token:
        load_dotenv()
        token = os.environ.get("BOT_TOKEN", "")
    # create TelegramBotWrapper instance
    # by default, read parameters in telegram_config.cfg
    tg_server = AiogramLlmBot(config_file_path=config_file_path)
    asyncio.run(tg_server.run_telegram_bot(token))


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    if len(sys.argv) > 2:
        run_server(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        run_server(sys.argv[1])
    else:
        run_server("")
