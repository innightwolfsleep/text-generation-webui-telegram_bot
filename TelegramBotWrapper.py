import io
import os.path
from threading import Thread, Lock, Event
from pathlib import Path
import json
import time
from re import split, sub
from os import listdir
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAudio
from telegram.ext import CallbackContext, Filters, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import Updater
from telegram.error import BadRequest
from telegram.constants import CHATACTION_TYPING
from typing import Dict
from deep_translator import GoogleTranslator as Translator

try:
    from extensions.telegram_bot.TelegramBotUser import TelegramBotUser as User
    import extensions.telegram_bot.TelegramBotGenerator as Generator
    from extensions.telegram_bot.TelegramBotSilero import Silero as Silero
except ImportError:
    from TelegramBotUser import TelegramBotUser as User
    import TelegramBotGenerator as Generator
    from TelegramBotSilero import Silero as Silero


class TelegramBotWrapper:
    # Default error messages
    GENERATOR_FAIL = "<GENERATION FAIL>"
    GENERATOR_EMPTY_ANSWER = "<EMPTY ANSWER>"
    UNKNOWN_TEMPLATE = "<UNKNOWN TEMPLATE>"
    UNKNOWN_USER = "<UNKNOWN USER>"
    # Various predefined data
    MODE_ADMIN = "admin"
    MODE_CHAT = "chat"
    MODE_CHAT_R = "chat-restricted"
    MODE_NOTEBOOK = "notebook"
    MODE_PERSONA = "persona"
    MODE_QUERY = "query"
    BTN_CONTINUE = 'Continue'
    BTN_NEXT = 'Next'
    BTN_DEL_WORD = 'Delete_one_word'
    BTN_REGEN = 'Regen'
    BTN_CUTOFF = 'Cutoff'
    BTN_DELETE = "Delete"
    BTN_RESET = 'Reset'
    BTN_DOWNLOAD = 'Download'
    BTN_LORE = 'Context'
    BTN_CHAR_LIST = 'Chars_list'
    BTN_CHAR_LOAD = 'Chars_load'
    BTN_MODEL_LIST = 'Model_list'
    BTN_MODEL_LOAD = 'Model_load'
    BTN_VOICE_LIST = 'Voice_list'
    BTN_VOICE_LOAD = 'Voice_load'
    BTN_PRESET_LIST = 'Presets_list'
    BTN_PRESET_LOAD = 'Preset_load'
    BTN_LANG_LIST = 'Language_list'
    BTN_LANG_LOAD = 'Language_load'
    BTN_OPTION = "options"
    GET_MESSAGE = "message"
    GENERATOR_MODE_NEXT = "/send_next_message"
    GENERATOR_MODE_CONTINUE = "/continue_last_message"
    # Supplementary structure
    # Rules for various mode. 0=False=Restricted, 1=True=Allowed
    user_rules = {
     # messages buttons
     BTN_NEXT: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 0, },
     BTN_CONTINUE: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_DEL_WORD: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_REGEN: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 0, MODE_QUERY: 1, },
     BTN_CUTOFF: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_OPTION: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     # option buttons
     BTN_CHAR_LIST: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 0, MODE_NOTEBOOK: 1, MODE_PERSONA: 0, MODE_QUERY: 1, },
     BTN_CHAR_LOAD: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 0, MODE_NOTEBOOK: 1, MODE_PERSONA: 0, MODE_QUERY: 1, },
     BTN_RESET: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_DOWNLOAD: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     BTN_LORE: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     BTN_LANG_LIST: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     BTN_LANG_LOAD: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     BTN_VOICE_LIST: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     BTN_VOICE_LOAD: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     BTN_PRESET_LIST: {MODE_ADMIN: 1, MODE_CHAT: 0, MODE_CHAT_R: 0, MODE_NOTEBOOK: 0, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_PRESET_LOAD: {MODE_ADMIN: 1, MODE_CHAT: 0, MODE_CHAT_R: 0, MODE_NOTEBOOK: 0, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_MODEL_LIST: {MODE_ADMIN: 1, MODE_CHAT: 0, MODE_CHAT_R: 0, MODE_NOTEBOOK: 0, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_MODEL_LOAD: {MODE_ADMIN: 1, MODE_CHAT: 0, MODE_CHAT_R: 0, MODE_NOTEBOOK: 0, MODE_PERSONA: 0, MODE_QUERY: 0, },
     BTN_DELETE: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
     # allow to get messages
     GET_MESSAGE: {MODE_ADMIN: 1, MODE_CHAT: 1, MODE_CHAT_R: 1, MODE_NOTEBOOK: 1, MODE_PERSONA: 1, MODE_QUERY: 1, },
    }
    # Internal, changeable settings
    replace_prefixes = ["!", "-"]  # Prefix to replace last message
    impersonate_prefixes = ["#", "+"]  # Prefix for "impersonate" message
    permanent_impersonate_prefixes = ["++"]  # Prefix for persistence "impersonate" message
    permanent_user_prefixes = ["+="]  # Prefix for replace username "impersonate" message
    permanent_contex_add = ["+-"]  # Prefix for adding string to context
    sd_api_prefixes = ["@", "📷", "📸", "📹", "🎥", "📽", ]  # Prefix for sd api generation
    sd_api_prompt_of = "Provide a detailed and vivid description of "
    sd_api_prompt_self = "Provide a detailed description of appearance, surroundings and what doing right now"
    # Language list
    language_dict = {"en": "🇬🇧", "ru": "🇷🇺", "ja": "🇯🇵", "fr": "🇫🇷", "es": "🇪🇸", "de": "🇩🇪", "th": "🇹🇭",
                     "tr": "🇹🇷", "it": "🇮🇹", "hi": "🇮🇳", "zh-CN": "🇨🇳", "ar": "🇸🇾"}
    # Set dummy obj for telegram updater
    updater = None
    # Define generator lock to prevent GPU overloading
    generator_lock = Lock()
    generation_timeout = 600
    # Bot message open/close html tags. Set ["", ""] to disable.
    html_tag = ["<pre>", "</pre>"]
    translate_html_tag = ['<span class="tg-spoiler">', '</span>']
    translation_as_hidden_text = "off"
    generation_params = {
        'max_new_tokens': 256,
        'seed': -1.0,
        'temperature': 0.7,
        'top_p': 0.1,
        'top_k': 40,
        'typical_p': 1,
        'repetition_penalty': 1.18,
        'encoder_repetition_penalty': 1,
        'no_repeat_ngram_size': 0,
        'min_length': 0,
        'do_sample': True,
        'penalty_alpha': 0,
        'num_beams': 1,
        'length_penalty': 1,
        'early_stopping': False,
        'add_bos_token': True,
        'ban_eos_token': False,
        'truncation_length': 1200,
        'custom_stopping_strings': '',
        'chat_prompt_size': 1200,
        'chat_generation_attempts': 1,
        'stop_at_newline': False,
        'skip_special_tokens': True,
    }

    # dict of User data dicts, here stored all users' session info.
    users: Dict[int, User] = {}

    # last message timestamp to avoid message flood.
    last_msg_timestamp: Dict[int, int] = {}
    # Delay between new messages to avoid flooding (sec)
    flood_avoid_delay = 10.0

    def __init__(self,
                 bot_mode="admin",
                 default_char="Example.yaml",
                 default_preset="LLaMA-Precise.txt",
                 model_lang="en",
                 user_lang="en",
                 characters_dir_path="characters",
                 presets_dir_path="presets",
                 history_dir_path="history",
                 token_file_path="telegram_token.txt",
                 admins_file_path="telegram_admins.txt",
                 users_file_path="telegram_users.txt",
                 config_file_path="telegram_config.cfg",
                 ):
        """
        Init telegram bot class. Use run_telegram_bot() to initiate bot.
        :param bot_mode: bot mode (chat, chat-restricted, notebook, persona). Default is "chat".
        :param default_char: name of default character.json file. Default is "chat".
        :param default_preset: name of default preset file.
        :param model_lang: language of model
        :param user_lang: language of conversation
        :param characters_dir_path: place where stored characters .json files. Default is "chat".
        :param presets_dir_path: path to presets generation presets.
        :param history_dir_path: place where stored chat history. Default is "extensions/telegram_bot/history".
        :param token_file_path: path to token file. Default is "extensions/telegram_bot/telegram_token.txt".
        :param admins_file_path: path to admins file - user separated by "\n"
        :param users_file_path: permitted users separated by "\n". If empty - no restriction
        :param config_file_path: path to config file
        :return: None
        """
        # Set paths to history, default token file, characters dir
        self.history_dir_path = history_dir_path
        self.characters_dir_path = characters_dir_path
        self.presets_dir_path = presets_dir_path
        self.token_file_path = token_file_path
        self.admins_file_path = admins_file_path
        self.users_file_path = users_file_path
        # Set bot mode
        self.bot_mode = bot_mode
        # Set default character json file
        self.default_char = default_char
        self.default_preset = default_preset
        # Set translator
        self.model_lang = model_lang
        self.user_lang = user_lang
        self.stopping_strings = []
        self.eos_token = None
        # Read config_file if existed, overwrite bot config
        self.load_config_file(config_file_path)
        self.load_preset(self.default_preset)
        self.silero = Silero()

    def load_config_file(self, config_file_path: str):
        if os.path.exists(config_file_path):
            with open(config_file_path, "r") as config_file_path:
                for s in config_file_path.read().replace("\r", "").split("\n"):
                    if "=" in s and s.split("=")[0] == "bot_mode":
                        self.bot_mode = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "default_preset":
                        self.default_preset = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "default_char":
                        self.default_char = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "model_lang":
                        self.model_lang = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "user_lang":
                        self.user_lang = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "html_tag_open":
                        self.html_tag[0] = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "html_tag_close":
                        self.html_tag[-1] = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "characters_dir_path":
                        self.characters_dir_path = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "presets_dir_path":
                        self.presets_dir_path = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "history_dir_path":
                        self.history_dir_path = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "token_file_path":
                        self.token_file_path = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "admins_file_path":
                        self.admins_file_path = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "users_file_path":
                        self.users_file_path = s.split("=")[-1]
                    if "=" in s and s.split("=")[0] == "translation_as_hidden_text":
                        self.translation_as_hidden_text = s.split("=")[-1].lower()
                    if "=" in s and s.split("=")[0] == "stopping_strings":
                        if s.split("=")[-1] == "None":
                            self.stopping_strings = []
                        else:
                            self.stopping_strings += "".join(s.split("=")[1:]).split(",")
                    if "=" in s and s.split("=")[0] == "eos_token":
                        if s.split("=")[-1] == "None":
                            self.eos_token = None
                        else:
                            self.eos_token += "".join(s.split("=")[1:]).split(",")

    # =============================================================================
    # Run bot with token! Initiate updater obj!
    def run_telegram_bot(self, bot_token=None, token_file_name=None):
        """
        Start the Telegram bot.
        :param bot_token: (str) The Telegram bot token. If not provided, try to read it from `token_file_name`.
        :param token_file_name: (str) The name of the file containing the bot token. Default is `None`.
        :return: None
        """
        if not bot_token:
            token_file_name = token_file_name or self.token_file_path
            with open(token_file_name, "r", encoding="utf-8") as f:
                bot_token = f.read().strip()
        self.updater = Updater(token=bot_token, use_context=True)
        self.updater.dispatcher.add_handler(
            CommandHandler("start", self.cb_start_command)),
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.text, self.cb_get_message))
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.document.mime_type("application/json"), self.cb_get_json_document))
        self.updater.dispatcher.add_handler(
            CallbackQueryHandler(self.cb_opt_button))
        self.updater.start_polling()
        Thread(target=self.no_sleep_callback).start()
        print("Telegram bot started!", self.updater)

    def no_sleep_callback(self):
        while True:
            try:
                self.updater.bot.send_message(chat_id=99999999999, text='One message every minute')
            except BadRequest:
                pass
            except Exception as error:
                print(error)
            time.sleep(60)

    # =============================================================================
    # Handlers
    def cb_start_command(self, upd, context):
        Thread(target=self.thread_welcome_message,
               args=(upd, context)).start()

    def cb_get_message(self, upd, context):
        Thread(target=self.thread_get_message, args=(upd, context)).start()

    def cb_opt_button(self, upd, context):
        Thread(target=self.thread_push_button, args=(upd, context)).start()

    def cb_get_json_document(self, upd, context):
        Thread(target=self.thread_get_json_document, args=(upd, context)).start()

    # =============================================================================
    # Additional telegram actions
    def thread_welcome_message(self, upd: Update, context: CallbackContext):
        chat_id = upd.effective_chat.id
        if not self.check_user_permission(chat_id):
            return False
        self.init_check_user(chat_id)
        send_text = self.make_template_message("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text, chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML")

    def clean_last_message_markup(self, context: CallbackContext, chat_id: int):
        if (chat_id in self.users and
                len(self.users[chat_id].msg_id) > 0):
            last_msg = self.users[chat_id].msg_id[-1]
            try:
                context.bot.editMessageReplyMarkup(
                    chat_id=chat_id, message_id=last_msg, reply_markup=None)
            except Exception as exception:
                print("last_message_markup_clean", exception)

    def make_template_message(self, request: str, chat_id: int, custom_string="") -> str:
        # create a message using default_messages_template or return UNKNOWN_TEMPLATE
        if chat_id in self.users:
            user = self.users[chat_id]
            if request in user.default_messages_template:
                msg = user.default_messages_template[request]
                msg = msg.replace("_CHAT_ID_", str(chat_id))
                msg = msg.replace("_NAME1_", user.name1)
                msg = msg.replace("_NAME2_", user.name2)
                msg = msg.replace("_CONTEXT_", user.context)
                msg = msg.replace("_GREETING_", self.prepare_text(user.greeting, user.language, "to_user"))
                msg = msg.replace("_CUSTOM_STRING_", self.prepare_text(custom_string, user.language, "to_user"))
                msg = msg.replace("_OPEN_TAG_", self.html_tag[0])
                msg = msg.replace("_CLOSE_TAG_", self.html_tag[1])
                return msg
            else:
                print(request, custom_string)
                return self.UNKNOWN_TEMPLATE
        else:
            print(request, custom_string)
            return self.UNKNOWN_USER

    # =============================================================================
    # Work with history! Init/load/save functions
    def parse_characters_dir(self) -> list:
        char_list = []
        for f in listdir(self.characters_dir_path):
            if f.endswith(('.json', '.yaml', '.yml')):
                char_list.append(f)
        return char_list

    def parse_presets_dir(self) -> list:
        preset_list = []
        for f in listdir(self.presets_dir_path):
            if f.endswith('.txt') or f.endswith('.yaml'):
                preset_list.append(f)
        return preset_list

    def init_check_user(self, chat_id):
        if chat_id not in self.users:
            # Load default
            self.users.update({chat_id: User()})
            self.users[chat_id].load_character_file(characters_dir_path=self.characters_dir_path,
                                                    char_file=self.default_char)
            self.users[chat_id].load_user_history(f'{self.history_dir_path}/{str(chat_id)}.json')
            self.users[chat_id].find_and_load_user_char_history(chat_id, self.history_dir_path)

    def thread_get_json_document(self, upd: Update, context: CallbackContext):
        chat_id = upd.message.chat.id
        if not self.check_user_permission(chat_id):
            return False
        self.init_check_user(chat_id)
        default_user_file_path = str(Path(f'{self.history_dir_path}/{str(chat_id)}.json'))
        with open(default_user_file_path, 'wb') as f:
            context.bot.get_file(upd.message.document.file_id).download(out=f)
        self.users[chat_id].load_user_history(default_user_file_path)
        if len(self.users[chat_id].history) > 0:
            last_message = self.users[chat_id].history[-1]
        else:
            last_message = "<no message in history>"
        send_text = self.make_template_message("hist_loaded", chat_id, last_message)
        context.bot.send_message(
            chat_id=chat_id, text=send_text,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML")

    def typing_status_start(self, context: CallbackContext, chat_id: int) -> Event:
        typing_active = Event()
        typing_active.set()
        Thread(target=self.thread_typing_status, args=(context, chat_id, typing_active)).start()
        return typing_active

    def thread_typing_status(self, context: CallbackContext, chat_id: int, typing_active: Event):
        limit_counter = int(self.generation_timeout / 6)
        while typing_active.is_set() and limit_counter > 0:
            context.bot.send_chat_action(chat_id=chat_id, action=CHATACTION_TYPING)
            time.sleep(6)
            limit_counter -= 1

    def check_user_permission(self, chat_id):
        # Read admins list
        if os.path.exists(self.users_file_path):
            with open(self.users_file_path, "r") as users_file:
                users_list = users_file.read().split()
        else:
            users_list = []
        # check
        if str(chat_id) in users_list or len(users_list) == 0:
            return True
        else:
            return False

    def check_user_flood(self, chat_id):
        if chat_id not in self.last_msg_timestamp:
            self.last_msg_timestamp.update({chat_id: time.time()})
            return True
        if time.time() - self.flood_avoid_delay > self.last_msg_timestamp[chat_id]:
            self.last_msg_timestamp.update({chat_id: time.time()})
            return True
        else:
            return False

    def send(self, context: CallbackContext, chat_id: int, text: str):
        user = self.users[chat_id]
        text = self.prepare_text(text, self.users[chat_id].language, "to_user")
        if user.silero_speaker == "None" or user.silero_model_id == "None":
            message = context.bot.send_message(text=text, chat_id=chat_id, parse_mode="HTML",
                                               reply_markup=self.get_chat_keyboard())
            return message
        else:
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                with open(audio_path, "rb") as audio:
                    message = context.bot.send_audio(chat_id=chat_id, audio=audio, caption=text,
                                                     filename=f"{user.name2}_to_{user.name1}.wav",
                                                     parse_mode="HTML", reply_markup=self.get_chat_keyboard())
            else:
                message = context.bot.send_message(text=text, chat_id=chat_id, parse_mode="HTML",
                                                   reply_markup=self.get_chat_keyboard())
                return message
            return message

    def edit(self, context: CallbackContext, upd: Update, chat_id: int, text: str, message_id: int):
        user = self.users[chat_id]
        text = self.prepare_text(text, user.language, "to_user")
        if upd.callback_query.message.text is not None:
            context.bot.editMessageText(text=text, chat_id=chat_id, parse_mode="HTML", message_id=message_id,
                                        reply_markup=self.get_chat_keyboard())
        if upd.callback_query.message.audio is not None \
                and user.silero_speaker != "None" \
                and user.silero_model_id != "None":
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                with open(audio_path, "rb") as audio:
                    media = InputMediaAudio(media=audio, filename=f"{user.name2}_to_{user.name1}.wav")
                    context.bot.edit_message_media(chat_id=chat_id, media=media, message_id=message_id,
                                                   reply_markup=self.get_chat_keyboard())
        if upd.callback_query.message.caption is not None:
            context.bot.editMessageCaption(chat_id=chat_id, caption=text, parse_mode="HTML", message_id=message_id,
                                           reply_markup=self.get_chat_keyboard())

    # =============================================================================
    # Message handler
    def thread_get_message(self, upd: Update, context: CallbackContext):
        # Extract user input and chat ID
        user_text = upd.message.text
        chat_id = upd.message.chat.id
        if not self.check_user_permission(chat_id):
            return False
        if not self.check_user_flood(chat_id):
            return False
        # Send "typing" message
        typing = self.typing_status_start(context, chat_id)
        try:
            if self.check_user_rule(chat_id=chat_id, option=self.GET_MESSAGE) is not True:
                return False
            self.init_check_user(chat_id)
            user = self.users[chat_id]
            # Generate answer and replace "typing" message with it
            user_text = self.prepare_text(user_text, self.users[chat_id].language, "to_model")
            answer, system_message = self.generate_answer(user_in=user_text, chat_id=chat_id)
            if system_message:
                context.bot.send_message(text=answer, chat_id=chat_id)
            else:
                message = self.send(text=answer, chat_id=chat_id, context=context)
                # Clear buttons on last message (if they exist in current thread)
                self.clean_last_message_markup(context, chat_id)
                # Add message ID to message history
                user.msg_id.append(message.message_id)
                # Save user history
                user.save_user_history(chat_id, self.history_dir_path)
        except Exception as e:
            print(e)
            raise e
        finally:
            typing.clear()

    # =============================================================================
    # button
    def thread_push_button(self, upd: Update, context: CallbackContext):
        query = upd.callback_query
        query.answer()
        chat_id = query.message.chat.id
        msg_id = query.message.message_id
        option = query.data
        if not self.check_user_permission(chat_id):
            return False
        # Send "typing" message
        typing = self.typing_status_start(context, chat_id)
        try:
            if chat_id not in self.users:
                self.init_check_user(chat_id)
            if msg_id not in self.users[chat_id].msg_id and option in \
                    [self.BTN_NEXT, self.BTN_CONTINUE, self.BTN_DEL_WORD, self.BTN_REGEN, self.BTN_CUTOFF]:
                send_text = self.make_template_message("mem_lost", chat_id)
                context.bot.editMessageText(
                    text=send_text, chat_id=chat_id, message_id=msg_id,
                    reply_markup=None, parse_mode="HTML")
            else:
                self.handle_option(option, chat_id, upd, context)
                self.users[chat_id].save_user_history(chat_id, self.history_dir_path)
        except Exception as e:
            print(e)
        finally:
            typing.clear()

    def handle_option(self, option, chat_id, upd, context):
        if option == self.BTN_RESET and self.check_user_rule(chat_id, option):
            self.reset_history_button(upd=upd, context=context)
        elif option == self.BTN_CONTINUE and self.check_user_rule(chat_id, option):
            self.continue_message_button(upd=upd, context=context)
        elif option == self.BTN_NEXT and self.check_user_rule(chat_id, option):
            self.next_message_button(upd=upd, context=context)
        elif option == self.BTN_DEL_WORD and self.check_user_rule(chat_id, option):
            self.delete_word_button(upd=upd, context=context)
        elif option == self.BTN_REGEN and self.check_user_rule(chat_id, option):
            self.regenerate_message_button(upd=upd, context=context)
        elif option == self.BTN_CUTOFF and self.check_user_rule(chat_id, option):
            self.cutoff_message_button(upd=upd, context=context)
        elif option == self.BTN_DOWNLOAD and self.check_user_rule(chat_id, option):
            self.download_json_button(upd=upd, context=context)
        elif option == self.BTN_OPTION and self.check_user_rule(chat_id, option):
            self.options_button(upd=upd, context=context)
        elif option == self.BTN_DELETE and self.check_user_rule(chat_id, option):
            self.delete_button(upd=upd, context=context)
        elif option.startswith(self.BTN_CHAR_LIST) and self.check_user_rule(chat_id, option):
            self.keyboard_characters_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_CHAR_LOAD) and self.check_user_rule(chat_id, option):
            self.load_character_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_PRESET_LIST) and self.check_user_rule(chat_id, option):
            self.keyboard_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_PRESET_LOAD) and self.check_user_rule(chat_id, option):
            self.load_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_MODEL_LIST) and self.check_user_rule(chat_id, option):
            self.keyboard_models_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_MODEL_LOAD) and self.check_user_rule(chat_id, option):
            self.load_model_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_LANG_LIST) and self.check_user_rule(chat_id, option):
            self.keyboard_language_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_LANG_LOAD) and self.check_user_rule(chat_id, option):
            self.load_language_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_VOICE_LIST) and self.check_user_rule(chat_id, option):
            self.keyboard_voice_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_VOICE_LOAD) and self.check_user_rule(chat_id, option):
            self.load_voice_button(upd=upd, context=context, option=option)

    def options_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        history_tokens = -1
        context_tokens = -1
        greeting_tokens = -1
        try:
            history_tokens = Generator.tokens_count("\n".join(user.history))
            context_tokens = Generator.tokens_count("\n".join(user.context))
            greeting_tokens = Generator.tokens_count("\n".join(user.greeting))
        except Exception as e:
            print("options_button tokens_count", e)

        send_text = f"""{user.name2} ({user.char_file}), 
Conversation length: {str(len(user.history))} messages, ({history_tokens} tokens).
Context:{context_tokens}, greeting:{greeting_tokens} tokens.
Voice: {user.silero_speaker}
Language: {user.language}"""
        context.bot.send_message(
            text=send_text, chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML")

    @staticmethod
    def delete_button(upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        message_id = upd.callback_query.message.message_id
        context.bot.deleteMessage(chat_id=chat_id, message_id=message_id)

    def next_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        # send "typing"
        self.clean_last_message_markup(context, chat_id)
        answer, _ = self.generate_answer(user_in=self.GENERATOR_MODE_NEXT, chat_id=chat_id)
        message = self.send(text=answer, chat_id=chat_id, context=context)
        self.users[chat_id].msg_id.append(message.message_id)
        user.save_user_history(chat_id, self.history_dir_path)

    def continue_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        message = upd.callback_query.message
        user = self.users[chat_id]
        # get answer and replace message text!
        answer, _ = self.generate_answer(user_in=self.GENERATOR_MODE_CONTINUE, chat_id=chat_id)
        self.edit(text=answer, chat_id=chat_id, message_id=message.message_id, context=context, upd=upd)
        self.users[chat_id].msg_id.append(message.message_id)
        user.save_user_history(chat_id, self.history_dir_path)

    def delete_word_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]

        # get and change last message
        last_message = user.history[-1]
        last_word = split(r"\n+| +", last_message)[-1]
        new_last_message = last_message[:-(len(last_word))]
        new_last_message = new_last_message.strip()
        user.history[-1] = new_last_message

        # If there is previous message - add buttons to previous message
        if user.msg_id:
            self.edit(text=user.history[-1], chat_id=chat_id, message_id=user.msg_id[-1], context=context, upd=upd)
        user.save_user_history(chat_id, self.history_dir_path)

    def regenerate_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        user = self.users[chat_id]
        # add pretty "retyping" to message text
        # remove last bot answer, read and remove last user reply
        user_in = user.truncate_history()
        # get answer and replace message text!
        answer, _ = self.generate_answer(user_in=user_in, chat_id=chat_id)
        self.edit(text=answer, chat_id=chat_id, message_id=msg.message_id, context=context, upd=upd)
        user.save_user_history(chat_id, self.history_dir_path)

    def cutoff_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        # Edit or delete last message ID (strict lines)
        last_msg_id = user.msg_id[-1]
        context.bot.deleteMessage(chat_id=chat_id, message_id=last_msg_id)
        # Remove last message and bot answer from history
        user.truncate()
        # If there is previous message - add buttons to previous message
        if user.msg_id:
            message_id = user.msg_id[-1]
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id, message_id=message_id,
                reply_markup=self.get_chat_keyboard())
        user.save_user_history(chat_id, self.history_dir_path)

    def download_json_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id

        if chat_id not in self.users:
            return

        user_file = io.StringIO(self.users[chat_id].to_json())
        send_caption = self.make_template_message("hist_to_chat", chat_id)
        context.bot.send_document(
            chat_id=chat_id, caption=send_caption, document=user_file,
            filename=self.users[chat_id].name2 + ".json")

    def reset_history_button(self, upd: Update, context: CallbackContext):
        # check if it is a callback_query or a command
        if upd.callback_query:
            chat_id = upd.callback_query.message.chat.id
        else:
            chat_id = upd.message.chat.id
        if chat_id not in self.users:
            return
        user = self.users[chat_id]
        if user.msg_id:
            self.clean_last_message_markup(context, chat_id)
        user.clear()
        user.load_character_file(self.characters_dir_path, user.char_file)
        send_text = self.make_template_message("mem_reset", chat_id)
        context.bot.send_message(chat_id=chat_id, text=send_text,
                                 reply_markup=self.get_options_keyboard(chat_id),
                                 parse_mode="HTML")

    # =============================================================================
    # switching keyboard
    def load_model_button(self, upd: Update, context: CallbackContext, option: str):
        if Generator.get_model_list is not None:
            model_list = Generator.get_model_list()
            model_file = model_list[int(option.replace(self.BTN_MODEL_LOAD, ""))]
            chat_id = upd.effective_chat.id
            send_text = "Loading " + model_file + ". 🪄"
            message_id = upd.callback_query.message.message_id
            context.bot.editMessageText(
                text=send_text, chat_id=chat_id, message_id=message_id,
                parse_mode="HTML")
            try:
                Generator.load_model(model_file)
                send_text = self.make_template_message(
                    request="model_loaded", chat_id=chat_id, custom_string=model_file)
                context.bot.editMessageText(
                    chat_id=chat_id, message_id=message_id,
                    text=send_text,
                    parse_mode="HTML", reply_markup=self.get_options_keyboard(chat_id))
            except Exception as e:
                print("model button error: ", e)
                context.bot.editMessageText(
                    chat_id=chat_id, message_id=message_id,
                    text="Error during " + model_file + " loading. ⛔",
                    parse_mode="HTML", reply_markup=self.get_options_keyboard(chat_id))
                raise e

    def keyboard_models_button(self, upd: Update, context: CallbackContext, option: str):
        if Generator.get_model_list() is not None:
            chat_id = upd.callback_query.message.chat.id
            msg = upd.callback_query.message
            model_list = Generator.get_model_list()
            if option == self.BTN_MODEL_LIST + self.BTN_OPTION:
                context.bot.editMessageReplyMarkup(
                    chat_id=chat_id, message_id=msg.message_id,
                    reply_markup=self.get_options_keyboard(chat_id))
                return
            shift = int(option.replace(self.BTN_MODEL_LIST, ""))
            characters_buttons = self.get_switch_keyboard(
                opt_list=model_list, shift=shift,
                data_list=self.BTN_MODEL_LIST,
                data_load=self.BTN_MODEL_LOAD)
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id, message_id=msg.message_id,
                reply_markup=characters_buttons)

    def load_presets_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        preset_char_num = int(option.replace(self.BTN_PRESET_LOAD, ""))
        self.default_preset = self.parse_presets_dir()[preset_char_num]
        self.load_preset(preset=self.default_preset)
        user = self.users[chat_id]
        send_text = f"""{user.name2}, 
        Conversation length{str(len(user.history))} messages.
        Voice: {user.silero_speaker}
        Language: {user.language}
        New preset: {self.default_preset}"""
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text, message_id=message_id, chat_id=chat_id,
            parse_mode="HTML", reply_markup=self.get_options_keyboard(chat_id))

    def load_preset(self, preset):
        preset_path = self.presets_dir_path + "/" + preset
        if os.path.exists(preset_path):
            with open(preset_path, "r") as preset_file:
                for line in preset_file.readlines():
                    name, value = line.replace("\n", "").replace("\r", "").replace(": ", "=").split("=")
                    if name in self.generation_params:
                        if type(self.generation_params[name]) is int:
                            self.generation_params[name] = int(float(value))
                        elif type(self.generation_params[name]) is float:
                            self.generation_params[name] = float(value)
                        elif type(self.generation_params[name]) is str:
                            self.generation_params[name] = str(value)
                        elif type(self.generation_params[name]) is bool:
                            self.generation_params[name] = bool(value)
                        elif type(self.generation_params[name]) is list:
                            self.generation_params[name] = list(value.split(","))

    def keyboard_presets_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == self.BTN_PRESET_LIST + self.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id, message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id))
            return
        #  get keyboard list shift
        shift = int(option.replace(self.BTN_PRESET_LIST, ""))
        preset_list = self.parse_presets_dir()
        characters_buttons = self.get_switch_keyboard(
            opt_list=preset_list, shift=shift,
            data_list=self.BTN_PRESET_LIST,
            data_load=self.BTN_PRESET_LOAD, keyboard_colum=3)
        context.bot.editMessageReplyMarkup(
            chat_id=chat_id, message_id=msg.message_id,
            reply_markup=characters_buttons)

    def load_character_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        char_num = int(option.replace(self.BTN_CHAR_LOAD, ""))
        char_list = self.parse_characters_dir()
        self.clean_last_message_markup(context, chat_id)
        self.init_check_user(chat_id)
        char_file = char_list[char_num]
        self.users[chat_id].load_character_file(characters_dir_path=self.characters_dir_path,
                                                char_file=char_file)
        #  If there was conversation with this char - load history
        self.users[chat_id].find_and_load_user_char_history(chat_id, self.history_dir_path)
        if len(self.users[chat_id].history) > 0:
            send_text = self.make_template_message("hist_loaded", chat_id, self.users[chat_id].history[-1])
        else:
            send_text = self.make_template_message("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text, chat_id=chat_id,
            parse_mode="HTML", reply_markup=self.get_options_keyboard(chat_id))

    def keyboard_characters_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == self.BTN_CHAR_LIST + self.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id, message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id))
            return
        #  get keyboard list shift
        shift = int(option.replace(self.BTN_CHAR_LIST, ""))
        char_list = self.parse_characters_dir()
        if shift == -9999 and self.users[chat_id].char_file in char_list:
            shift = char_list.index(self.users[chat_id].char_file)
        #  create chars list
        characters_buttons = self.get_switch_keyboard(
            opt_list=char_list, shift=shift,
            data_list=self.BTN_CHAR_LIST,
            data_load=self.BTN_CHAR_LOAD)
        context.bot.editMessageReplyMarkup(
            chat_id=chat_id, message_id=msg.message_id,
            reply_markup=characters_buttons)

    def load_language_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        lang_num = int(option.replace(self.BTN_LANG_LOAD, ""))
        language = list(self.language_dict.keys())[lang_num]
        self.users[chat_id].language = language
        send_text = f"""{user.name2}, 
        Conversation length{str(len(user.history))} messages.
        Voice: {user.silero_speaker}
        Language: {user.language} (NEW)"""
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text, message_id=message_id, chat_id=chat_id,
            parse_mode="HTML", reply_markup=self.get_options_keyboard(chat_id))

    def keyboard_language_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == self.BTN_LANG_LIST + self.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id, message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id))
            return
        #  get keyboard list shift
        shift = int(option.replace(self.BTN_LANG_LIST, ""))
        #  create list
        lang_buttons = self.get_switch_keyboard(
            opt_list=list(self.language_dict.keys()), shift=shift,
            data_list=self.BTN_LANG_LIST,
            data_load=self.BTN_LANG_LOAD,
            keyboard_colum=4)
        context.bot.editMessageReplyMarkup(
            chat_id=chat_id, message_id=msg.message_id,
            reply_markup=lang_buttons)

    def load_voice_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        male = Silero.voices[user.language]["male"]
        female = Silero.voices[user.language]["female"]
        voice_dict = ["None"] + male + female
        voice_num = int(option.replace(self.BTN_VOICE_LOAD, ""))
        user.silero_speaker = voice_dict[voice_num]
        user.silero_model_id = Silero.voices[user.language]["model"]
        send_text = f"""{user.name2}, 
        Conversation length{str(len(user.history))} messages.
        Voice: {user.silero_speaker} (NEW)
        Language: {user.language}"""
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text, message_id=message_id, chat_id=chat_id,
            parse_mode="HTML", reply_markup=self.get_options_keyboard(chat_id))

    def keyboard_voice_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == self.BTN_VOICE_LIST + self.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id, message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id))
            return
        #  get keyboard list shift
        shift = int(option.replace(self.BTN_VOICE_LIST, ""))
        #  create list
        user = self.users[chat_id]
        male = list(map(lambda x: x + "🚹", Silero.voices[user.language]["male"]))
        female = list(map(lambda x: x + "🚺", Silero.voices[user.language]["female"]))
        voice_dict = ["🔇None"] + male + female
        voice_buttons = self.get_switch_keyboard(
            opt_list=list(voice_dict), shift=shift,
            data_list=self.BTN_VOICE_LIST,
            data_load=self.BTN_VOICE_LOAD,
            keyboard_colum=4)
        context.bot.editMessageReplyMarkup(
            chat_id=chat_id, message_id=msg.message_id,
            reply_markup=voice_buttons)

    # =============================================================================
    # answer generator
    def generate_answer(self, user_in, chat_id) -> tuple[str, False]:
        answer = self.GENERATOR_FAIL
        user = self.users[chat_id]

        try:
            # acquire generator lock if we can
            self.generator_lock.acquire(timeout=self.generation_timeout)
            # if generation will fail, return "fail" answer

            # Preprocessing: add user_in to history in right order:
            if user_in[:2] in self.permanent_impersonate_prefixes:
                # If user_in starts with perm_prefix - just replace name2
                user.name2 = user_in[2:]
                return "New name: " + user.name2, True
            if self.bot_mode in [self.MODE_QUERY]:
                user.history = []
            if self.bot_mode == self.MODE_NOTEBOOK:
                # If notebook mode - append to history only user_in, no additional preparing;
                user.user_in.append(user_in)
                user.history.append('')
                user.history.append(user_in)
            elif user_in == self.GENERATOR_MODE_NEXT:
                # if user_in is "" - no user text, it is like continue generation
                # adding "" history line to prevent bug in history sequence, add "name2:" prefix for generation
                user.user_in.append(user_in)
                user.history.append("")
                user.history.append(user.name2 + ":")
            elif user_in == self.GENERATOR_MODE_CONTINUE:
                # if user_in is "" - no user text, it is like continue generation
                # adding "" history line to prevent bug in history sequence, add "name2:" prefix for generation
                pass
            elif user_in[0] in self.impersonate_prefixes:
                # If user_in starts with prefix - impersonate-like (if you try to get "impersonate view")
                # adding "" line to prevent bug in history sequence, user_in is prefix for bot answer
                user.user_in.append(user_in)
                user.history.append("")
                user.history.append(user_in[1:] + ":")
            elif user_in[0] in self.replace_prefixes:
                # If user_in starts with replace_prefix - fully replace last message
                user.user_in.append(user_in)
                user.history[-1] = user_in[1:]
                return user.history[-1], False
            else:
                # If not notebook/impersonate/continue mode then ordinary chat preparing
                # add "name1&2:" to user and bot message (generation from name2 point of view);
                user.user_in.append(user_in)
                user.history.append(user.name1 + ": " + user_in)
                user.history.append(user.name2 + ":")

            # Set eos_token and stopping_strings.
            stopping_strings = self.stopping_strings.copy()
            eos_token = self.eos_token
            if self.bot_mode in [self.MODE_CHAT, self.MODE_CHAT_R, self.MODE_ADMIN]:
                stopping_strings += ["\n" + user.name1 + ":", "\n" + user.name2 + ":", ]

            # Make prompt: context + example + conversation history
            available_len = self.generation_params["truncation_length"]
            prompt = ""
            context = f"{user.context.strip()}\n"
            context_len = Generator.tokens_count(context)
            if available_len >= context_len:
                available_len -= context_len

            example = user.example + "\n<START>\n"
            greeting = "\n" + user.name2 + ": " + user.greeting
            conversation = [example, greeting] + user.history

            for s in reversed(conversation):
                s = "\n" + s
                s_len = Generator.tokens_count(s)
                if available_len >= s_len:
                    prompt = s + prompt
                    available_len -= s_len
                else:
                    break
            prompt = context + prompt.replace("\n\n", "\n")
            # Generate!
            answer = Generator.get_answer(prompt=prompt,
                                          generation_params=self.generation_params,
                                          user=json.loads(user.to_json()),
                                          eos_token=eos_token,
                                          stopping_strings=stopping_strings,
                                          default_answer=answer,
                                          turn_template=user.turn_template)
            # If generation result zero length - return  "Empty answer."
            if len(answer) < 1:
                answer = self.GENERATOR_EMPTY_ANSWER
            # Final return
            if answer not in [self.GENERATOR_EMPTY_ANSWER, self.GENERATOR_FAIL]:
                # if everything ok - add generated answer in history and return last
                for end in stopping_strings:
                    if answer.endswith(end):
                        answer = answer[:-len(end)]
                user.history[-1] = user.history[-1] + " " + answer
            return user.history[-1], False
        except Exception as exception:
            print("generate_answer", exception)
        finally:
            # anyway, release generator lock. Then return
            self.generator_lock.release()

    def prepare_text(self, original_text, user_language="en", direction="to_user"):
        text = original_text
        # translate
        if self.model_lang != user_language:
            try:
                if direction == "to_model":
                    text = Translator(source=user_language, target=self.model_lang).translate(text)
                elif direction == "to_user":
                    text = Translator(source=self.model_lang, target=user_language).translate(text)
            except Exception as e:
                text = "can't translate text:" + str(text)
                print("translator_error", e)
        # Add HTML tags and other...
        if direction not in ["to_model", "no_html"]:
            text = text.replace("#", "&#35;").replace("<", "&#60;").replace(">", "&#62;")
            original_text = original_text.replace("#", "&#35;").replace("<", "&#60;").replace(">", "&#62;")
            if self.model_lang != user_language and direction == "to_user" and self.translation_as_hidden_text == "on":
                text = self.html_tag[0] + original_text + self.html_tag[1] + "\n" + \
                       self.translate_html_tag[0] + text + self.translate_html_tag[1]
            else:
                text = self.html_tag[0] + text + self.html_tag[1]
        return text

    # =============================================================================
    # load characters char_file from ./characters

    def check_user_rule(self, chat_id, option):
        option = sub(r"[0123456789-]", "", option)
        if option.endswith(self.BTN_OPTION):
            option = self.BTN_OPTION
        # Read admins list
        if os.path.exists(self.admins_file_path):
            with open(self.admins_file_path, "r") as admins_file:
                admins_list = admins_file.read().split()
        else:
            admins_list = []
        # check admin rules
        if chat_id in admins_list or self.bot_mode == self.MODE_ADMIN:
            return bool(self.user_rules[option][self.MODE_ADMIN])
        else:
            return bool(self.user_rules[option][self.bot_mode])

    def get_options_keyboard(self, chat_id=0):
        keyboard_raw = []
        # get language
        if chat_id in self.users:
            language = self.users[chat_id].language
        else:
            language = "en"
        language_flag = self.language_dict[language]
        # get voice
        if chat_id in self.users:
            voice_str = self.users[chat_id].silero_speaker
            if voice_str == "None":
                voice = "🔇"
            else:
                voice = "🔈"
        else:
            voice = "🔇"

        if self.check_user_rule(chat_id, self.BTN_DOWNLOAD):
            keyboard_raw.append(InlineKeyboardButton(
                text="💾Save", callback_data=self.BTN_DOWNLOAD))
        #if self.check_user_rule(chat_id, self.BTN_LORE):
        #    keyboard_raw.append(InlineKeyboardButton(
        #        text="📜Lore", callback_data=self.BTN_LORE))
        if self.check_user_rule(chat_id, self.BTN_CHAR_LIST):
            keyboard_raw.append(InlineKeyboardButton(
                text="🎭Chars", callback_data=self.BTN_CHAR_LIST + "-9999"))
        if self.check_user_rule(chat_id, self.BTN_RESET):
            keyboard_raw.append(InlineKeyboardButton(
                text="⚠Reset", callback_data=self.BTN_RESET))
        if self.check_user_rule(chat_id, self.BTN_LANG_LIST):
            keyboard_raw.append(InlineKeyboardButton(
                text=language_flag + "Language", callback_data=self.BTN_LANG_LIST + "0"))
        if self.check_user_rule(chat_id, self.BTN_VOICE_LIST):
            keyboard_raw.append(InlineKeyboardButton(
                text=voice + "Voice", callback_data=self.BTN_VOICE_LIST + "0"))
        if self.check_user_rule(chat_id, self.BTN_PRESET_LIST):
            keyboard_raw.append(InlineKeyboardButton(
                text="🔧Presets", callback_data=self.BTN_PRESET_LIST + "0"))
        if self.check_user_rule(chat_id, self.BTN_MODEL_LIST):
            keyboard_raw.append(InlineKeyboardButton(
                text="🔨Model", callback_data=self.BTN_MODEL_LIST + "0"))
        if self.check_user_rule(chat_id, self.BTN_DELETE):
            keyboard_raw.append(InlineKeyboardButton(
                text="❌Close", callback_data=self.BTN_DELETE))
        return InlineKeyboardMarkup([keyboard_raw])

    def get_chat_keyboard(self, chat_id=0):
        keyboard_raw = []
        if self.check_user_rule(chat_id, self.BTN_NEXT):
            keyboard_raw.append(InlineKeyboardButton(
                text="▶Next", callback_data=self.BTN_NEXT))
        if self.check_user_rule(chat_id, self.BTN_CONTINUE):
            keyboard_raw.append(InlineKeyboardButton(
                text="➡Continue", callback_data=self.BTN_CONTINUE))
        if self.check_user_rule(chat_id, self.BTN_DEL_WORD):
            keyboard_raw.append(InlineKeyboardButton(
                text="⬅Del word", callback_data=self.BTN_DEL_WORD))
        if self.check_user_rule(chat_id, self.BTN_REGEN):
            keyboard_raw.append(InlineKeyboardButton(
                text="♻Regenerate", callback_data=self.BTN_REGEN))
        if self.check_user_rule(chat_id, self.BTN_CUTOFF):
            keyboard_raw.append(InlineKeyboardButton(
                text="✖Cutoff", callback_data=self.BTN_CUTOFF))
        if self.check_user_rule(chat_id, self.BTN_OPTION):
            keyboard_raw.append(InlineKeyboardButton(
                text="⚙Options", callback_data=self.BTN_OPTION))
        return InlineKeyboardMarkup([keyboard_raw])

    def get_switch_keyboard(self,
                            opt_list: list,
                            shift: int,
                            data_list: str,
                            data_load: str,
                            keyboard_rows=6,
                            keyboard_colum=2
                            ):
        # find shift
        opt_list_length = len(opt_list)
        keyboard_length = keyboard_rows * keyboard_colum
        if shift >= opt_list_length - keyboard_length:
            shift = opt_list_length - keyboard_length
        if shift < 0:
            shift = 0
        # append list
        characters_buttons = []
        column = 0
        for i in range(shift, keyboard_length + shift):
            if i >= len(opt_list):
                break
            if column == 0:
                characters_buttons.append([])
            column += 1
            if column >= keyboard_colum:
                column = 0
            characters_buttons[-1].append(InlineKeyboardButton(
                text=f"{opt_list[i]}",
                callback_data=f"{data_load}{str(i)}"))
            i += 1
        # add switch buttons
        begin_shift = 0
        l_shift = shift - keyboard_length
        l_shift_3 = shift - keyboard_length * 3
        r_shift = shift + keyboard_length
        r_shift_3 = shift + keyboard_length * 3
        end_shift = opt_list_length - keyboard_length
        switch_buttons = [
            InlineKeyboardButton(
                text="⏮",
                callback_data=data_list + str(begin_shift)),
            InlineKeyboardButton(
                text="⏪",
                callback_data=data_list + str(l_shift_3)),
            InlineKeyboardButton(
                text="◀",
                callback_data=data_list + str(l_shift)),
            InlineKeyboardButton(
                text="🔺",
                callback_data=data_list + self.BTN_OPTION),
            InlineKeyboardButton(
                text="▶",
                callback_data=data_list + str(r_shift)),
            InlineKeyboardButton(
                text="⏩",
                callback_data=data_list + str(r_shift_3)),
            InlineKeyboardButton(
                text="⏭",
                callback_data=data_list + str(end_shift)),
        ]
        characters_buttons.append(switch_buttons)
        # add new keyboard to message!
        return InlineKeyboardMarkup(characters_buttons)
