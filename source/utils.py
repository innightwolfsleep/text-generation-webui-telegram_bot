import json
import logging
import asyncio

from functools import wraps, partial
from os import listdir
from os.path import exists, normpath
from re import sub
from typing import Dict

from deep_translator import GoogleTranslator as Translator

try:
    import extensions.telegram_bot.source.text_process as tp
    import extensions.telegram_bot.source.const as const
    from extensions.telegram_bot.source.conf import cfg
    from extensions.telegram_bot.source.user import User as User
except ImportError:
    import source.text_process as tp
    import source.const as const
    from source.conf import cfg
    from source.user import User as User


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        target_func = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, target_func)

    return run


@async_wrap
def translate_text(text: str, source="en", target="en"):
    return Translator(source=source, target=target).translate(text)


async def prepare_text(original_text: str, user: User, direction="to_user"):
    text = original_text
    # translate
    if cfg.llm_lang != user.language:
        try:
            if direction == "to_model":
                text = await translate_text(text=text, source=user.language, target=cfg.llm_lang)
            elif direction == "to_user":
                text = await translate_text(text=text, source=cfg.llm_lang, target=user.language)
        except Exception as exception:
            text = "can't translate text:" + str(text)
            logging.error("translator_error:\n" + str(exception) + "\n" + str(exception.args))
    # Add HTML tags and other...
    if direction not in ["to_model", "no_html"]:
        text = text.replace("#", "&#35;").replace("<", "&#60;").replace(">", "&#62;")
        original_text = original_text.replace("#", "&#35;").replace("<", "&#60;").replace(">", "&#62;")
        if len(original_text) > 2000:
            original_text = original_text[:2000]
        if len(text) > 2000:
            text = text[:2000]
        if cfg.llm_lang != user.language and direction == "to_user" and cfg.translation_as_hidden_text == "on":
            text = (
                cfg.html_tag[0]
                + original_text
                + cfg.html_tag[1]
                + "\n"
                + cfg.translate_html_tag[0]
                + text
                + cfg.translate_html_tag[1]
            )
        else:
            if len(text) > 4000:
                text = text[:4000]
            text = cfg.html_tag[0] + text + cfg.html_tag[1]
    return text


def parse_characters_dir() -> list:
    char_list = []
    for f in listdir(cfg.characters_dir_path):
        if f.endswith((".json", ".yaml", ".yml")):
            char_list.append(f)
    return char_list


def parse_presets_dir() -> list:
    preset_list = []
    for f in listdir(cfg.presets_dir_path):
        if f.endswith(".txt") or f.endswith(".yaml"):
            preset_list.append(f)
    return preset_list


# User checking rules
def check_user_permission(chat_id):
    # Read admins list
    if exists(cfg.users_file_path):
        with open(normpath(cfg.users_file_path), "r") as users_file:
            users_list = users_file.read().split()
    else:
        users_list = []
    # check
    if str(chat_id) in users_list or len(users_list) == 0:
        return True
    else:
        return False


def check_user_rule(chat_id, option):
    if exists(cfg.user_rules_file_path):
        with open(normpath(cfg.user_rules_file_path), "r") as user_rules_file:
            user_rules = json.loads(user_rules_file.read())
    # if checked button with numeral postfix  - delete numerals
    option = sub(r"[0123456789-]", "", option)
    if option.endswith(const.BTN_OPTION):
        option = const.BTN_OPTION
    # Read admins list
    if exists(cfg.admins_file_path):
        with open(normpath(cfg.admins_file_path), "r") as admins_file:
            admins_list = admins_file.read().split()
    else:
        admins_list = []
    # check admin rules
    if str(chat_id) in admins_list or cfg.bot_mode == const.MODE_ADMIN:
        return bool(user_rules[option][const.MODE_ADMIN])
    else:
        return bool(user_rules[option][cfg.bot_mode])


def init_check_user(users: Dict[int, User], chat_id):
    if chat_id not in users:
        # Load default
        users.update({chat_id: User()})
        users[chat_id].user_id = chat_id
        users[chat_id].load_character_file(
            characters_dir_path=cfg.characters_dir_path,
            char_file=cfg.character_file,
        )
        users[chat_id].load_user_history(f"{cfg.history_dir_path}/{str(chat_id)}.json")
        users[chat_id].find_and_load_user_char_history(chat_id, cfg.history_dir_path)


def get_conversation_info(user: User):
    history_tokens = -1
    context_tokens = -1
    greeting_tokens = -1
    conversation_tokens = -1
    try:
        history_tokens = tp.generator.get_tokens_count(user.history_as_str())
        context_tokens = tp.generator.get_tokens_count(user.context)
        greeting_tokens = tp.generator.get_tokens_count(user.greeting)
        conversation_tokens = history_tokens + context_tokens + greeting_tokens
    except Exception as e:
        logging.error("options_button tokens_count" + str(e))

    max_token_param = "truncation_length"
    max_tokens = cfg.generation_params[max_token_param] if max_token_param in cfg.generation_params else "???"
    return (
        f"{user.name2}\n"
        f"Conversation length {str(conversation_tokens)}/{max_tokens} tokens.\n"
        f"(context {(str(context_tokens))}, "
        f"greeting {(str(greeting_tokens))}, "
        f"messages {(str(history_tokens))})\n"
        f"Voice: {user.silero_speaker}\n"
        f"Language: {user.language}"
    )
