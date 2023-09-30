from pydantic import BaseModel, Field
from typing import List, Dict
import logging
import os
import json

# Set logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y.%m.%d %I:%M:%S %p",
    level=logging.INFO,
)


class Config(BaseModel):
    flood_avoid_delay: float = Field(default=10.0, description="Delay between new messages to avoid flooding (sec)")
    generation_timeout: int = Field(default=300, description="Timeout for text generator")

    # Single shot prefixes
    replace_prefixes: List = Field(default=["!", "-"], description="Prefix to replace last message")
    impersonate_prefixes: List = Field(default=["#", "+"], description="Prefix for 'impersonate' message")
    # Prefix for persistence "impersonate" message
    permanent_change_name1_prefixes: List = Field(default=["--"], description="Prefix to replace name1")
    permanent_change_name2_prefixes: List = Field(default=["++"], description="Prefix to replace name2")
    permanent_add_context_prefixes: List = Field(default=["=="], description="Prefix to add in context")

    sd_api_prefixes: List = Field(default=["📷", "📸", "📹", "🎥", "📽", ],
                                  description="Prefix to generate image via SD API")
    sd_api_prompt_of: str = "Appearance of OBJECT:"
    sd_api_prompt_self: str = "Detailed description of surroundings:"

    html_tag = Field(default=["<pre>", "</pre>"], description="html tags for ordinary text")
    translate_html_tag = Field(default=['<span class="tg-spoiler">', "</span>"],
                               description="html tags for translated text")
    translation_as_hidden_text = Field(default="on", description="if 'on' translation showing after original message "
                                                                 "inside translate_html_tag. "
                                                                 "If 'off' - only translated text.")
    language_dict: Dict[str, str] = Field(default={
        "en": "🇬🇧",
        "ru": "🇷🇺",
        "ja": "🇯🇵",
        "fr": "🇫🇷",
        "es": "🇪🇸",
        "de": "🇩🇪",
        "th": "🇹🇭",
        "tr": "🇹🇷",
        "it": "🇮🇹",
        "hi": "🇮🇳",
        "zh-CN": "🇨🇳",
        "ar": "🇸🇾",
    }, description="Language list for translator")

    # Set internal config vars
    history_dir_path = "history"
    characters_dir_path = "characters"
    presets_dir_path = "presets"
    token_file_path = "telegram_token.txt"
    admins_file_path = "telegram_admins.txt"
    users_file_path = "telegram_users.txt"
    generator_params_file_path = "generator_params.json"
    user_rules_file_path = "telegram_user_rules.json"
    sd_api_url = "http://127.0.0.1:7860"
    sd_config_file_path = "sd_config.json"
    proxy_url = ""
    # Set bot mode
    bot_mode = "admin"
    user_name_template = ""  # template for username. "" - default (You), FIRSTNAME, LASTNAME, USERNAME, ID
    generator_script = ""  # mode loaded from config
    model_path = ""
    # Set default character json file
    character_file = "Example.yaml"
    preset_file = "LLaMA-Creative.txt"
    # Set translator
    model_lang = "en"
    user_lang = "en"
    # generator params!
    generation_params = {}

    # generator initiate

    def load(self, config_file_path: str):
        self.load_config_file(config_file_path)
        self.load_generation_params(self.generator_params_file_path)
        self.load_preset(self.preset_file)

    def load_config_file(self, config_file_path: str):
        if os.path.exists(config_file_path):
            with open(config_file_path, "r") as config_file_path:
                config = json.loads(config_file_path.read())
                self.bot_mode = config.get("bot_mode", self.bot_mode)
                self.user_name_template = config.get("user_name_template", self.user_name_template)
                self.generator_script = config.get("generator_script", self.generator_script)
                self.model_path = config.get("model_path", self.model_path)
                self.preset_file = config.get("preset_file", self.preset_file)
                self.character_file = config.get("character_file", self.character_file)
                self.model_lang = config.get("model_lang", self.model_lang)
                self.user_lang = config.get("user_lang", self.user_lang)
                self.characters_dir_path = config.get("characters_dir_path", self.characters_dir_path)
                self.presets_dir_path = config.get("presets_dir_path", self.presets_dir_path)
                self.history_dir_path = config.get("history_dir_path", self.history_dir_path)
                self.token_file_path = config.get("token_file_path", self.token_file_path)
                self.admins_file_path = config.get("admins_file_path", self.admins_file_path)
                self.users_file_path = config.get("users_file_path", self.users_file_path)
                self.generator_params_file_path = config.get(
                    "generator_params_file_path", self.generator_params_file_path
                )
                self.user_rules_file_path = config.get("user_rules_file_path", self.user_rules_file_path)
                self.sd_api_url = config.get("sd_api_url", self.sd_api_url)
                self.sd_config_file_path = config.get("sd_config_file_path", self.sd_config_file_path)
                cfg.translation_as_hidden_text = config.get(
                    "translation_as_hidden_text", cfg.translation_as_hidden_text
                )
                self.proxy_url = config.get("proxy_url", self.proxy_url)
        else:
            logging.error("Cant find config_file " + config_file_path)

    def load_generation_params(self, generator_params_file_path=""):
        if generator_params_file_path is not None:
            self.generator_params_file_path = generator_params_file_path
        # Load user generator parameters
        if os.path.exists(self.generator_params_file_path):
            with open(self.generator_params_file_path, "r") as params_file:
                self.generation_params = json.loads(params_file.read())
        else:
            logging.error("Cant find generator_params_file")

    def load_preset(self, preset_file=""):
        if preset_file is not None:
            self.preset_file = preset_file
        preset_path = self.presets_dir_path + "/" + self.preset_file
        if os.path.exists(preset_path):
            with open(preset_path, "r") as preset_file:
                for line in preset_file.readlines():
                    name, value = line.replace("\n", "").replace("\r", "").replace(": ", "=").split("=")
                    if name in self.generation_params:
                        if type(self.generation_params[name]) == int:
                            self.generation_params[name] = int(float(value))
                        elif type(self.generation_params[name]) == float:
                            self.generation_params[name] = float(value)
                        elif type(self.generation_params[name]) == str:
                            self.generation_params[name] = str(value)
                        elif type(self.generation_params[name]) == bool:
                            self.generation_params[name] = bool(value)
                        elif type(self.generation_params[name]) == list:
                            self.generation_params[name] = list(value.split(","))


cfg = Config()
