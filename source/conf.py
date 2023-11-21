import json
import logging
from os.path import exists, normpath
from typing import List, Dict

from pydantic import BaseModel, Field

# Set logging
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y.%m.%d %I:%M:%S %p",
    level=logging.INFO,
)


class Config(BaseModel):
    flood_avoid_delay: float = Field(default=10.0, description="Delay between new messages to avoid flooding (sec)")
    answer_delay: float = Field(default=0.0, description="Additional delay between request and answer.")
    generation_timeout: int = Field(default=300, description="Timeout for text generator")
    only_mention_in_chat: int = Field(default=True, description="If true - answer only for @bot mentions")

    # Single shot prefixes
    replace_prefixes: List = Field(default=["!", "-"], description="Prefix to replace last message")
    impersonate_prefixes: List = Field(default=["#", "+"], description="Prefix for 'impersonate' message")
    # Prefix for persistence "impersonate" message
    permanent_change_name1_prefixes: List = Field(default=["--"], description="Prefix to replace name1")
    permanent_change_name2_prefixes: List = Field(default=["++"], description="Prefix to replace name2")
    permanent_add_context_prefixes: List = Field(default=["==", "="], description="Prefix to add in context")

    sd_api_prefixes: List = Field(
        default=[
            "📷",
            "📸",
            "📹",
            "🎥",
            "📽",
        ],
        description="Prefix to generate image via SD API",
    )
    sd_api_prompt_of: str = Field(
        default="Detailed description of OBJECT:", description="sd api - prompt for ordinary request"
    )
    sd_api_prompt_self: str = Field(
        default="Detailed description of surroundings:", description="sd api - prompt for empty request"
    )

    html_tag: list = Field(default=["<pre>", "</pre>"], description="html tags for ordinary text")
    translate_html_tag: list = Field(
        default=['<span class="tg-spoiler">', "</span>"], description="html tags for translated text"
    )
    translation_as_hidden_text: str = Field(
        default="on",
        description="if 'on' translation showing after original message "
        "inside translate_html_tag. "
        "If 'off' - only translated text.",
    )
    language_dict: Dict[str, str] = Field(
        default={
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
        },
        description="Language list for translator",
    )

    # Set internal config vars Field(default=, description=)
    prompt_template: str = Field(default="configs/prompt_templates/empty.json", description="prompt_template")
    history_dir_path: str = Field(default="history", description="history")
    characters_dir_path: str = Field(default="characters", description="characters")
    presets_dir_path: str = Field(default="presets", description="")
    token_file_path: str = Field(default="telegram_token.txt", description="")
    admins_file_path: str = Field(default="telegram_admins.txt", description="")
    users_file_path: str = Field(default="telegram_users.txt", description="")
    generator_params_file_path: str = Field(default="generator_params.json", description="")
    user_rules_file_path: str = Field(default="telegram_user_rules.json", description="")
    sd_api_url: str = Field(default="http://127.0.0.1:7860", description="")
    sd_config_file_path: str = Field(default="sd_config.json", description="")
    proxy_url: str = Field(default="", description="")
    # Set bot mode
    bot_mode: str = Field(default="admin", description="")
    user_name_template: str = Field(
        default="", description="template for username. " " - default (You), FIRSTNAME, LASTNAME, USERNAME, ID"
    )
    generator_script: str = Field(default="", description="mode loaded from config")
    llm_path: str = Field(default="", description="")
    context_prompt_begin: str = Field(default="", description="")
    context_prompt_end: str = Field(default="", description="")
    bot_prompt_begin: str = Field(default="", description="")
    bot_prompt_end: str = Field(default="", description="")
    user_prompt_begin: str = Field(default="", description="")
    user_prompt_end: str = Field(default="", description="")
    # Set default character json file
    character_file: str = Field(default="Example.yaml", description="")
    preset_file: str = Field(default="LLaMA-Creative.txt", description="")
    # Set translator
    llm_lang: str = Field(default="en", description="")
    user_lang: str = Field(default="en", description="")
    # generator params!
    generation_params: dict = Field(default={}, description="")

    # generator initiate

    def load(self, config_file_path: str):
        logging.info(f"### Config LOAD config_file_path: {config_file_path} ###")
        self.load_config_file(config_file_path)
        logging.info(f"### Config LOAD prompt_template: {self.prompt_template} ###")
        self.load_prompt_template(self.prompt_template)
        logging.info(f"### Config LOAD generation_params: {self.generator_params_file_path} ###")
        self.load_generation_params(self.generator_params_file_path)
        logging.info(f"### Config LOAD load_preset: {self.preset_file} ###")
        self.load_preset(self.preset_file)
        logging.info(f"### Config LOAD DONE ###")

    def load_config_file(self, config_file_path: str):
        if exists(normpath(config_file_path)):
            with open(normpath(config_file_path), "r") as config_file_path:
                config = json.loads(config_file_path.read())
                self.bot_mode = config.get("bot_mode", self.bot_mode)
                self.user_name_template = config.get("user_name_template", self.user_name_template)
                self.generator_script = config.get("generator_script", self.generator_script)
                self.llm_path = config.get("model_path", self.llm_path)
                self.presets_dir_path = config.get("presets_dir_path", self.presets_dir_path)
                self.preset_file = config.get("preset_file", self.preset_file)
                self.characters_dir_path = config.get("characters_dir_path", self.characters_dir_path)
                self.character_file = config.get("character_file", self.character_file)
                self.llm_lang = config.get("model_lang", self.llm_lang)
                self.user_lang = config.get("user_lang", self.user_lang)
                self.prompt_template = config.get("prompt_template", self.prompt_template)
                self.history_dir_path = config.get("history_dir_path", self.history_dir_path)
                self.token_file_path = config.get("token_file_path", self.token_file_path)
                self.admins_file_path = config.get("admins_file_path", self.admins_file_path)
                self.users_file_path = config.get("users_file_path", self.users_file_path)
                self.generator_params_file_path = config.get(
                    "generator_params_file_path", self.generator_params_file_path
                )
                self.user_rules_file_path = config.get("user_rules_file_path", self.user_rules_file_path)
                self.sd_api_url = config.get("sd_api_url", self.sd_api_url)
                self.sd_api_prompt_of = config.get("sd_api_prompt_of", self.sd_api_prompt_of)
                self.sd_api_prompt_self = config.get("sd_api_prompt_self", self.sd_api_prompt_self)
                self.sd_config_file_path = config.get("sd_config_file_path", self.sd_config_file_path)
                self.only_mention_in_chat = config.get("only_mention_in_chat", self.only_mention_in_chat)
                self.html_tag = config.get("html_tag", self.html_tag)
                self.translate_html_tag = config.get("translate_html_tag", self.translate_html_tag)
                cfg.translation_as_hidden_text = config.get(
                    "translation_as_hidden_text", cfg.translation_as_hidden_text
                )
                self.proxy_url = config.get("proxy_url", self.proxy_url)
        else:
            logging.error("Cant find config_file " + config_file_path)

    def load_prompt_template(self, prompt_template_path=""):
        if not prompt_template_path:
            prompt_template_path = self.prompt_template
        if exists(normpath(prompt_template_path)):
            with open(normpath(prompt_template_path), "r") as prompt_template_file:
                prompt_template = json.loads(prompt_template_file.read())
                self.context_prompt_begin = prompt_template.get("context_prompt_begin", self.context_prompt_begin)
                self.context_prompt_end = prompt_template.get("context_prompt_end", self.context_prompt_end)
                self.bot_prompt_begin = prompt_template.get("bot_prompt_begin", self.bot_prompt_begin)
                self.bot_prompt_end = prompt_template.get("bot_prompt_end", self.bot_prompt_end)
                self.user_prompt_begin = prompt_template.get("user_prompt_begin", self.user_prompt_begin)
                self.user_prompt_end = prompt_template.get("user_prompt_end", self.user_prompt_end)

    def load_generation_params(self, generator_params_file_path=""):
        if generator_params_file_path is not None:
            self.generator_params_file_path = generator_params_file_path
        # Load user generator parameters
        if exists(self.generator_params_file_path):
            with open(normpath(self.generator_params_file_path), "r") as params_file:
                self.generation_params = json.loads(params_file.read())
        else:
            logging.error("Cant find generator_params_file")

    def load_preset(self, preset_file=""):
        if preset_file is not None:
            self.preset_file = preset_file
        preset_path = self.presets_dir_path + "/" + self.preset_file
        if exists(preset_path):
            with open(normpath(preset_path), "r") as preset_file:
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
