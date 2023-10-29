import json
import logging
import os
from os import listdir
from re import sub
from typing import Dict

from deep_translator import GoogleTranslator as Translator

try:
    import extensions.telegram_bot.source.const as const
    from extensions.telegram_bot.source.conf import cfg
    from extensions.telegram_bot.source.user import User as User
except ImportError:
    import source.const as const
    from source.conf import cfg
    from source.user import User as User, User


def prepare_text(original_text: str, user: User, direction="to_user"):
    text = original_text
    # translate
    if cfg.model_lang != user.language:
        try:
            if direction == "to_model":
                text = Translator(source=user.language, target=cfg.model_lang).translate(text)
            elif direction == "to_user":
                text = Translator(source=cfg.model_lang, target=user.language).translate(text)
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
        if cfg.model_lang != user.language and direction == "to_user" and cfg.translation_as_hidden_text == "on":
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
    if os.path.exists(cfg.users_file_path):
        with open(cfg.users_file_path, "r") as users_file:
            users_list = users_file.read().split()
    else:
        users_list = []
    # check
    if str(chat_id) in users_list or len(users_list) == 0:
        return True
    else:
        return False


def check_user_rule(chat_id, option):
    if os.path.exists(cfg.user_rules_file_path):
        with open(cfg.user_rules_file_path, "r") as user_rules_file:
            user_rules = json.loads(user_rules_file.read())
    option = sub(r"[0123456789-]", "", option)
    if option.endswith(const.BTN_OPTION):
        option = const.BTN_OPTION
    # Read admins list
    if os.path.exists(cfg.admins_file_path):
        with open(cfg.admins_file_path, "r") as admins_file:
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
