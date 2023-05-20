import io
import os.path
from threading import Thread, Lock
from pathlib import Path
import json
import time
from re import split
from os import listdir
from os.path import exists
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, Filters, CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import Updater
from telegram.error import BadRequest
from typing import Dict
from deep_translator import GoogleTranslator as Translator

try:
    from extensions.telegram_bot.TelegramBotUser import TelegramBotUser as User
    import extensions.telegram_bot.TelegramBotGenerator as Generator
except ImportError:
    from TelegramBotUser import TelegramBotUser as User
    import TelegramBotGenerator as Generator


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
    BTN_RESET = 'Reset'
    BTN_DELETE = "Delete"
    BTN_DOWNLOAD = 'Download'
    BTN_CHAR_LIST = 'Chars_list'
    BTN_CHAR_LOAD = 'Chars_load:'
    BTN_MODEL_LIST = 'Model_list:'
    BTN_MODEL_LOAD = 'Model_load:'
    BTN_PRESET_LIST = 'Presets_list:'
    BTN_PRESET_LOAD = 'Preset_load:'
    BTN_LANG_LIST = 'Language_list:'
    BTN_LANG_LOAD = 'Language_load:'
    BTN_OPTION = "options"
    GENERATOR_MODE_NEXT = "/send_next_message"
    GENERATOR_MODE_CONTINUE = "/continue_last_message"
    # Supplementary structure
    # Internal, changeable settings
    replace_prefixes = ["!", "-"]  # Prefix to replace last message
    impersonate_prefixes = ["#", "+"]  # Prefix for "impersonate" message
    # Language list
    language_dict = {"en": "🇬🇧", "ru": "🇷🇺", "ja": "🇯🇵", "fr": "🇫🇷", "es": "🇪🇸", "de": "🇩🇪", "th": "🇹🇭",
                     "tr": "🇹🇷", "it": "🇮🇹", "hi": "🇮🇳", "zh-CN": "🇨🇳", "ar": "🇸🇾"}
    # Set dummy obj for telegram updater
    updater = None
    # Define generator lock to prevent GPU overloading
    generator_lock = Lock()
    # Bot message open/close html tags. Set ["", ""] to disable.
    html_tag = ["<pre>", "</pre>"]
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
        :param config_file_path: path to config file
        :return: None
        """
        # Set paths to history, default token file, characters dir
        self.history_dir_path = history_dir_path
        self.characters_dir_path = characters_dir_path
        self.presets_dir_path = presets_dir_path
        self.token_file_path = token_file_path
        # Set bot mode
        self.bot_mode = bot_mode
        # Set default character json file
        self.default_char = default_char
        self.default_preset = default_preset
        # Set translator
        self.model_lang = model_lang
        self.user_lang = user_lang
        # Read admins list
        if os.path.exists(admins_file_path):
            with open(admins_file_path, "r") as admins_file:
                self.admins_list = admins_file.read().split()
        else:
            self.admins_list = []
        # Read config_file if existed, overwrite bot config
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
        self.load_preset(self.default_preset)

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
        Thread(target=self.send_welcome_message,
               args=(upd, context)).start()

    def cb_get_message(self, upd, context):
        Thread(target=self.tr_get_message, args=(upd, context)).start()

    def cb_opt_button(self, upd, context):
        Thread(target=self.tr_opt_button, args=(upd, context)).start()

    def cb_get_json_document(self, upd, context):
        Thread(target=self.load_json_document, args=(upd, context)).start()

    # =============================================================================
    # Additional telegram actions
    def send_welcome_message(self, upd: Update, context: CallbackContext):
        chat_id = upd.effective_chat.id
        self.init_check_user(chat_id)
        send_text = self.message_template_generator("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text, chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML")

    def last_message_markup_clean(self, context: CallbackContext, chat_id: int):
        if (chat_id in self.users and
                len(self.users[chat_id].msg_id) > 0):
            last_msg = self.users[chat_id].msg_id[-1]
            try:
                context.bot.editMessageReplyMarkup(
                    chat_id=chat_id, message_id=last_msg, reply_markup=None)
            except Exception as exception:
                print("last_message_markup_clean", exception)

    def message_template_generator(self, request: str, chat_id: int, custom_string="") -> str:
        # create a message using default_messages_template or return UNKNOWN_TEMPLATE
        if chat_id in self.users:
            user = self.users[chat_id]
            if request in user.default_messages_template:
                msg = user.default_messages_template[request]
                msg = msg.replace("_CHAT_ID_", str(chat_id))
                msg = msg.replace("_NAME1_", user.name1)
                msg = msg.replace("_NAME2_", user.name2)
                msg = msg.replace("_CONTEXT_", user.context)
                msg = msg.replace("_GREETING_", self.text_preparing(user.greeting, user.language, "to_user"))
                msg = msg.replace("_CUSTOM_STRING_", self.text_preparing(custom_string, user.language, "to_user"))
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
            if f.endswith('.txt'):
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

    def load_json_document(self, upd: Update, context: CallbackContext):
        chat_id = upd.message.chat.id
        self.init_check_user(chat_id)
        default_user_file_path = str(Path(f'{self.history_dir_path}/{str(chat_id)}.json'))
        with open(default_user_file_path, 'wb') as f:
            context.bot.get_file(upd.message.document.file_id).download(out=f)
        self.users[chat_id].load_user_history(default_user_file_path)
        if len(self.users[chat_id].history) > 0:
            last_message = self.users[chat_id].history[-1]
        else:
            last_message = "<no message in history>"
        send_text = self.message_template_generator("hist_loaded", chat_id, last_message)
        context.bot.send_message(
            chat_id=chat_id, text=send_text,
            reply_markup=self.get_options_keyboard(chat_id),
            parse_mode="HTML")

    # =============================================================================
    # Message handler
    def tr_get_message(self, upd: Update, context: CallbackContext):
        # Extract user input and chat ID
        user_text = upd.message.text
        chat_id = upd.message.chat.id
        self.init_check_user(chat_id)
        # Send "typing" message
        send_text = self.message_template_generator("typing", chat_id)
        message = context.bot.send_message(
            text=send_text, chat_id=chat_id, parse_mode="HTML")
        # Generate answer and replace "typing" message with it
        user_text = self.text_preparing(user_text, self.users[chat_id].language, "to_model")
        answer = self.generate_answer(user_in=user_text, chat_id=chat_id)
        answer = self.text_preparing(answer, self.users[chat_id].language, "to_user")
        context.bot.editMessageText(
            text=answer, chat_id=chat_id, message_id=message.message_id,
            parse_mode="HTML", reply_markup=self.get_keyboard())
        # Clear buttons on last message (if they exist in current thread)
        self.last_message_markup_clean(context, chat_id)
        # Add message ID to message history
        self.users[chat_id].msg_id.append(message.message_id)
        # Save user history
        self.users[chat_id].save_user_history(chat_id, self.history_dir_path)
        return True

    # =============================================================================
    # button
    def tr_opt_button(self, upd: Update, context: CallbackContext):
        query = upd.callback_query
        query.answer()
        chat_id = query.message.chat.id
        msg_id = query.message.message_id
        msg_text = query.message.text
        option = query.data
        if chat_id not in self.users:
            self.init_check_user(chat_id)
        if msg_id not in self.users[chat_id].msg_id \
                and option in [self.BTN_NEXT, self.BTN_CONTINUE, self.BTN_DEL_WORD, self.BTN_REGEN, self.BTN_CUTOFF]:
            send_text = self.text_preparing(msg_text, self.users[chat_id].language, "to_user") \
                        + self.message_template_generator("mem_lost", chat_id)
            context.bot.editMessageText(
                text=send_text, chat_id=chat_id, message_id=msg_id,
                reply_markup=None, parse_mode="HTML")
        else:
            self.handle_option(option, upd, context)
            self.users[chat_id].save_user_history(chat_id, self.history_dir_path)

    def handle_option(self, option, upd, context):
        if option == self.BTN_RESET:
            self.reset_history_button(upd=upd, context=context)
        elif option == self.BTN_CONTINUE:
            self.continue_message_button(upd=upd, context=context)
        elif option == self.BTN_NEXT:
            self.next_message_button(upd=upd, context=context)
        elif option == self.BTN_DEL_WORD:
            self.delete_word_button(upd=upd, context=context)
        elif option == self.BTN_REGEN:
            self.regenerate_message_button(upd=upd, context=context)
        elif option == self.BTN_CUTOFF:
            self.cutoff_message_button(upd=upd, context=context)
        elif option == self.BTN_DOWNLOAD:
            self.download_json_button(upd=upd, context=context)
        elif option == self.BTN_OPTION:
            self.options_button(upd=upd, context=context)
        elif option == self.BTN_DELETE:
            self.delete_button(upd=upd, context=context)
        elif option.startswith(self.BTN_CHAR_LIST):
            self.keyboard_characters_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_CHAR_LOAD):
            self.load_character_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_PRESET_LIST):
            self.keyboard_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_PRESET_LOAD):
            self.load_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_MODEL_LIST):
            self.keyboard_models_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_MODEL_LOAD):
            self.load_model_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_LANG_LIST):
            self.keyboard_language_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_LANG_LOAD):
            self.load_language_button(upd=upd, context=context, option=option)

    def options_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        send_text = "Conversation with: " + user.name2 + ", " + str(len(user.history)) + " messages."
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

        # send "typing"
        self.last_message_markup_clean(context, chat_id)
        send_text = self.message_template_generator("typing", chat_id)
        message = context.bot.send_message(
            text=send_text, chat_id=chat_id,
            parse_mode="HTML")

        # get answer and replace message text!
        answer = self.generate_answer(user_in=self.GENERATOR_MODE_NEXT, chat_id=chat_id)
        answer = self.text_preparing(answer, self.users[chat_id].language, "to_user")
        context.bot.editMessageText(
            text=answer, chat_id=chat_id, message_id=message.message_id,
            reply_markup=self.get_keyboard(), parse_mode="HTML")
        self.users[chat_id].msg_id.append(message.message_id)

    def continue_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        message = upd.callback_query.message

        # add pretty "typing" to message text
        send_text = self.text_preparing(message.text, self.users[chat_id].language, "to_user")
        send_text += self.message_template_generator('typing', chat_id)
        context.bot.editMessageText(
            text=send_text, chat_id=chat_id, message_id=message.message_id,
            parse_mode="HTML")

        # get answer and replace message text!
        answer = self.generate_answer(user_in=self.GENERATOR_MODE_CONTINUE, chat_id=chat_id)
        answer = self.text_preparing(answer, self.users[chat_id].language, "to_user")
        context.bot.editMessageText(
            text=answer, chat_id=chat_id, message_id=message.message_id,
            reply_markup=self.get_keyboard(), parse_mode="HTML")
        self.users[chat_id].msg_id.append(message.message_id)

    def delete_word_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        # get and change last message
        last_message = user.history[-1]
        last_word = split(r"\n+| +", last_message)[-1]
        new_last_message = last_message[:-(len(last_word))]
        new_last_message = new_last_message.strip()
        user.history[-1] = new_last_message
        send_text = self.text_preparing(new_last_message, self.users[chat_id].language, "to_user")
        # If there is previous message - add buttons to previous message
        if user.msg_id:
            message_id = user.msg_id[-1]
            context.bot.editMessageText(
                text=send_text, chat_id=chat_id, message_id=message_id,
                reply_markup=self.get_keyboard(), parse_mode="HTML")
        self.users[chat_id].save_user_history(chat_id, self.history_dir_path)

    def regenerate_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        user = self.users[chat_id]
        # add pretty "retyping" to message text
        send_text = self.text_preparing(msg.text, self.users[chat_id].language, "to_user")
        send_text += self.message_template_generator('retyping', chat_id)
        context.bot.editMessageText(
            text=send_text, chat_id=chat_id, message_id=msg.message_id,
            parse_mode="HTML")

        # remove last bot answer, read and remove last user reply
        user_in, _ = user.pop()

        # get answer and replace message text!
        answer = self.generate_answer(user_in=user_in, chat_id=chat_id)
        answer = self.text_preparing(answer, self.users[chat_id].language, "to_user")
        context.bot.editMessageText(
            text=answer, chat_id=chat_id, message_id=msg.message_id,
            reply_markup=self.get_keyboard(), parse_mode="HTML")
        user.msg_id.append(msg.message_id)

    def cutoff_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        # Edit or delete last message ID (strict lines)
        last_msg_id = user.msg_id[-1]
        context.bot.deleteMessage(chat_id=chat_id, message_id=last_msg_id)
        # Remove last message and bot answer from history
        user.pop()
        # If there is previous message - add buttons to previous message
        if user.msg_id:
            message_id = user.msg_id[-1]
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id, message_id=message_id,
                reply_markup=self.get_keyboard())
        self.users[chat_id].save_user_history(chat_id, self.history_dir_path)

    def download_json_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id

        if chat_id not in self.users:
            return

        user_file = io.StringIO(self.users[chat_id].to_json())
        send_caption = self.message_template_generator("hist_to_chat", chat_id)
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
            self.last_message_markup_clean(context, chat_id)
        user.reset_history()
        send_text = self.message_template_generator("mem_reset", chat_id)
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
                send_text = self.message_template_generator(
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
        send_text = self.message_template_generator("preset_loaded", chat_id, self.default_preset)
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text, message_id=message_id, chat_id=chat_id,
            parse_mode="HTML", reply_markup=self.get_options_keyboard(chat_id))

    def load_preset(self, preset):
        preset_path = self.presets_dir_path + "/" + preset
        if os.path.exists(preset_path):
            with open(preset_path, "r") as preset_file:
                for line in preset_file.readlines():
                    name, value = line.replace("\n", "").replace("\r", "").split("=")
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
        self.last_message_markup_clean(context, chat_id)
        self.init_check_user(chat_id)
        char_file = char_list[char_num]
        self.users[chat_id].load_character_file(characters_dir_path=self.characters_dir_path,
                                                char_file=char_file)
        #  If there was conversation with this char - load history
        self.users[chat_id].find_and_load_user_char_history(chat_id, self.history_dir_path)
        if len(self.users[chat_id].history) > 0:
            send_text = self.message_template_generator(
                "hist_loaded", chat_id, self.users[chat_id].history[-1])
        else:
            send_text = self.message_template_generator(
                "char_loaded", chat_id)
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text, message_id=message_id, chat_id=chat_id,
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
        print(shift, self.users[chat_id].char_file)
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
        lang_num = int(option.replace(self.BTN_LANG_LOAD, ""))
        language = list(self.language_dict.keys())[lang_num]
        self.users[chat_id].language = language
        send_text = "New language: " + self.html_tag[0] + language + self.html_tag[-1]
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

    # =============================================================================
    # answer generator
    def generate_answer(self, user_in, chat_id):
        # if generation will fail, return "fail" answer
        answer = self.GENERATOR_FAIL
        user = self.users[chat_id]

        # Preprocessing: add user_in to history in right order:
        if self.bot_mode in [self.MODE_QUERY]:
            user.history = []
        if self.bot_mode == "notebook":
            # If notebook mode - append to history only user_in, no additional preparing;
            user.user_in.append(user_in)
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
            return user.history[-1]
        else:
            # If not notebook/impersonate/continue mode then ordinary chat preparing
            # add "name1&2:" to user and bot message (generation from name2 point of view);
            user.user_in.append(user_in)
            user.history.append(user.name1 + ": " + user_in)
            user.history.append(user.name2 + ":")

        # Set eos_token and stopping_strings.
        stopping_strings = []
        eos_token = None
        if self.bot_mode in [self.MODE_CHAT, self.MODE_CHAT_R, self.MODE_ADMIN]:
            eos_token = None
            stopping_strings = ["\n" + user.name1 + ":", "\n" + user.name2 + ":", ]

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

        try:
            # acquire generator lock if we can
            self.generator_lock.acquire(timeout=600)
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
        except Exception as exception:
            print("generate_answer", exception)
        finally:
            # anyway, release generator lock. Then return
            self.generator_lock.release()
            if answer not in [self.GENERATOR_EMPTY_ANSWER, self.GENERATOR_FAIL]:
                # if everything ok - add generated answer in history and return last
                for end in stopping_strings:
                    if answer.endswith(end):
                        answer = answer[:-len(end)]
                user.history[-1] = user.history[-1] + " " + answer
            return user.history[-1]

    def text_preparing(self, text, user_language="en", direction="to_user"):
        # translate
        if self.model_lang != user_language:
            if direction == "to_model":
                text = Translator(
                    source=user_language,
                    target=self.model_lang).translate(text)
            elif direction == "to_user":
                text = Translator(
                    source=self.model_lang,
                    target=user_language).translate(text)

        # Add HTML tags and other...
        if direction not in ["to_model", "no_html"]:
            text = text.replace("#", "&#35;").replace("<", "&#60;").replace(">", "&#62;")
            text = self.html_tag[0] + text + self.html_tag[1]
        return text

    # =============================================================================
    # load characters char_file from ./characters

    def get_options_keyboard(self, chat_id=0):
        if chat_id in self.users:
            language = self.users[chat_id].language
        else:
            language = "en"
        language_flag = self.language_dict[language]
        if self.bot_mode == self.MODE_ADMIN or str(chat_id) in self.admins_list:
            return InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="💾Save", callback_data=self.BTN_DOWNLOAD),
                        InlineKeyboardButton(
                            text="🎭Chars", callback_data=self.BTN_CHAR_LIST + "-9999"),
                        InlineKeyboardButton(
                            text="🗑Reset", callback_data=self.BTN_RESET),
                        InlineKeyboardButton(
                            text=language_flag + "Language", callback_data=self.BTN_LANG_LIST + "0"),
                        InlineKeyboardButton(
                            text="🔧Presets", callback_data=self.BTN_PRESET_LIST + "0"),
                        InlineKeyboardButton(
                            text="🔨Model", callback_data=self.BTN_MODEL_LIST + "0"),
                        InlineKeyboardButton(
                            text="❌Close", callback_data=self.BTN_DELETE)
                    ]
                ]
            )
        elif self.bot_mode == self.MODE_CHAT:
            return InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="💾Save", callback_data=self.BTN_DOWNLOAD),
                        InlineKeyboardButton(
                            text="🎭Chars", callback_data=self.BTN_CHAR_LIST + "-9999"),
                        InlineKeyboardButton(
                            text="🗑Reset", callback_data=self.BTN_RESET),
                        InlineKeyboardButton(
                            text=language_flag + "Language", callback_data=self.BTN_LANG_LIST + "0"),
                        InlineKeyboardButton(
                            text="❌Close", callback_data=self.BTN_DELETE)
                    ]
                ]
            )
        else:
            return None

    def get_keyboard(self, chat_id=0):
        if self.bot_mode in [self.MODE_ADMIN, self.MODE_CHAT] or str(chat_id) in self.admins_list:
            return InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="▶Next", callback_data=self.BTN_NEXT),
                        InlineKeyboardButton(
                            text="➡Continue", callback_data=self.BTN_CONTINUE),
                        InlineKeyboardButton(
                            text="⬅Del word", callback_data=self.BTN_DEL_WORD),
                        InlineKeyboardButton(
                            text="♻Regenerate", callback_data=self.BTN_REGEN),
                        InlineKeyboardButton(
                            text="✂Cutoff", callback_data=self.BTN_CUTOFF),
                        InlineKeyboardButton(
                            text="⚙Options", callback_data=self.BTN_OPTION),
                    ]
                ]
            )
        elif self.bot_mode == self.MODE_CHAT_R:
            return InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="▶Next", callback_data=self.BTN_NEXT),
                        InlineKeyboardButton(
                            text="➡Continue", callback_data=self.BTN_CONTINUE),
                        InlineKeyboardButton(
                            text="⬅Del word", callback_data=self.BTN_DEL_WORD),
                        InlineKeyboardButton(
                            text="🔄Regenerate", callback_data=self.BTN_REGEN),
                        InlineKeyboardButton(
                            text="✂Cutoff", callback_data=self.BTN_CUTOFF),
                        InlineKeyboardButton(
                            text="⚙Options", callback_data=self.BTN_OPTION),
                    ]
                ]
            )
        elif self.bot_mode == self.MODE_NOTEBOOK:
            return InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="▶Next", callback_data=self.BTN_NEXT),
                        InlineKeyboardButton(
                            text="🚫Reset memory", callback_data=self.BTN_RESET),
                    ]
                ]
            )
        elif self.bot_mode == self.MODE_PERSONA:
            return None

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
