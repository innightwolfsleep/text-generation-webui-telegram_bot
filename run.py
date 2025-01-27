import os
import argparse
import asyncio
from dotenv import load_dotenv
from main import AiogramLlmBot

# Default configuration file path
DEFAULT_CONFIG_FILE_PATH = "configs/app_config.json"


def run_server(token: str, config_file_path: str = DEFAULT_CONFIG_FILE_PATH):
    """
    Run the Telegram bot server.

    Args:
        token (str): The Telegram bot token.
        config_file_path (str): Path to the configuration file. Defaults to DEFAULT_CONFIG_FILE_PATH.
    """
    if not token:
        # Load environment variables from .env file
        load_dotenv()
        token = os.environ.get("BOT_TOKEN", "")
        if not token:
            raise ValueError("Bot token not provided and not found in environment variables.")

    # Create an instance of TelegramBotWrapper
    tg_server = AiogramLlmBot(config_file_path=config_file_path)
    asyncio.run(tg_server.run_telegram_bot(token))


def main():
    """
    Main function to handle command-line arguments and start the bot.
    """
    parser = argparse.ArgumentParser(description="Run a Telegram bot using LLM.")

    # Argument for the bot token (long: --token, short: -t)
    parser.add_argument(
        "-t", "--token",
        type=str,
        help="The Telegram bot token. If not provided, it will be loaded from environment or telegram_token.txt.",
        default=""
    )

    # Argument for the configuration file path (long: --config, short: -c)
    parser.add_argument(
        "-c", "--config",
        type=str,
        help=f"Path to the configuration file. Default: {DEFAULT_CONFIG_FILE_PATH}",
        default=DEFAULT_CONFIG_FILE_PATH
    )

    # Parse the arguments
    args = parser.parse_args()

    # Run the server with the provided arguments
    run_server(args.token, args.config)


if __name__ == "__main__":
    main()