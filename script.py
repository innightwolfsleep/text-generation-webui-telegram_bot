from threading import Thread, Lock
from pathlib import Path
import json
import yaml
import time
import server
from os import listdir
from os.path import exists
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, Filters, CommandHandler, MessageHandler, CallbackQueryHandler, Updater
from modules.text_generation import generate_reply
from modules import shared
from typing import Dict

try:
    from deep_translator import GoogleTranslator
except Exception as error:
    print(f"cant import translator: {error}")

params = {
    # Telegram bot token! Ask https://t.me/BotFather to get! By default, reading in telegram_token.txt
    "token": "TELEGRAM_TOKEN",
    # chat, chat-restricted, notebook, persona
    'bot_mode': "chat",
    # delete (remove cut text) or cross (cross-cut text)
    'cutoff_mode': "delete",
    # character json file from text-generation-webui/characters
    'character_to_load': "Example.yaml",
    # settings for auto-translate
    'user_language': "en",
}


class TelegramBotWrapper:
    # Default error messages
    GENERATOR_FAIL = "<GENERATION FAIL>"
    GENERATOR_EMPTY_ANSWER = "<EMPTY ANSWER>"
    UNKNOWN_TEMPLATE = "<UNKNOWN TEMPLATE>"
    # Various predefined data
    MODE_CHAT = "chat"
    MODE_CHAT_R = "chat-restricted"
    MODE_NOTEBOOK = "notebook"
    MODE_PERSONA = "persona"
    CUTOFF_DELETE = "delete"
    CUTOFF_STRICT = "cross"
    BTN_CONTINUE = 'Continue'
    BTN_REGEN = 'Regen'
    BTN_CUTOFF = 'Cutoff'
    BTN_RESET = 'Reset'
    BTN_DOWNLOAD = 'Download'
    BTN_CHAR_LIST = 'Chars'
    BTN_CHAR_LOAD = 'Char_load'
    # Supplementary structure
    # Internal, changeable settings
    impersonate_prefix = "#"  # Prefix for "impersonate" messages during chatting
    default_messages_template = {  # dict of messages templates for various situations. Use _VAR_ replacement
        "mem_lost": "<b>MEMORY LOST!</b>\nSend /start or any text for new session.",  # refers to non-existing
        "retyping": "<i>_NAME2_ retyping...</i>",  # added when "regenerate button" working
        "typing": "<i>_NAME2_ typing...</i>",  # added when generating working
        "char_loaded": "_NAME2_ LOADED!\n_OPEN_TAG__GREETING__CLOSE_TAG_ ",  # When new char loaded
        "mem_reset": "MEMORY RESET!\nSend /start or any text for new session.",  # When history cleared
        "hist_to_chat": "To load history - forward message to this chat",  # download history
        "hist_loaded": "_NAME2_ LOADED!\n_OPEN_TAG__GREETING__CLOSE_TAG_"
                       "\n\nLAST MESSAGE:\n_OPEN_TAG__CUSTOM_STRING__CLOSE_TAG_",  # load history
    }
    generation_params = {
        'max_new_tokens': 200,
        'seed': -1.0,
        'temperature': 0.72,
        'top_p': 0.73,
        'top_k': 0,
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
        'truncation_length': 1024,
        'custom_stopping_strings': [],
        'end_of_turn': '',
        'chat_prompt_size': 1024,
        'chat_generation_attempts': 1,
        'stop_at_newline': False,
        'skip_special_tokens': True,
    }

    class User:
        """
        Class stored individual tg user info (history, message sequence, etc...) and provide some actions
        """

        def __init__(self, name1="You", name2="Bot", context="", greeting="Hi!"):
            """
            Init User class with default attribute
            :param name1: username
            :param name2: current character name
            :param context: context of conversation, example: "Conversation between Bot and You"
            :param greeting: just greeting message from bot
            :return: None
            """
            self.name1: str = name1
            self.name2: str = name2
            self.context: str = context
            self.user_in: list = []  # "user input history": [["Hi!","Who are you?"]], need for regenerate option
            self.history: list = []  # "history": [["Hi!", "Hi there!","Who are you?", "I am you assistant."]],
            self.msg_id: list = []  # "msg_id": [143, 144, 145, 146],
            self.greeting: str = greeting

        def pop(self):
            #  Converts all data to json string
            user_in = self.user_in.pop()
            msg_id = self.msg_id.pop()
            self.history = self.history[:-2]
            return user_in, msg_id

        def reset_history(self):
            #  clear all user history
            self.user_in = []
            self.history = []
            self.msg_id = []

        def to_json(self):
            #  Converts all data to json string
            return json.dumps({
                "name1": self.name1,
                "name2": self.name2,
                "context": self.context,
                "user_in": self.user_in,
                "history": self.history,
                "msg_id": self.msg_id,
                "greeting": self.greeting,
            })

        def from_json(self, s: str):
            #  Converts json string to internal values
            data = json.loads(s)
            try:
                self.name1 = data["name1"]
                self.name2 = data["name2"]
                self.context = data["context"]
                self.user_in = data["user_in"]
                self.history = data["history"]
                self.msg_id = data["msg_id"]
                self.greeting = data["greeting"]
                return True
            except Exception as error:
                print("from_json", error)
                return False

    # dict of User data dicts, here stored all users' session info.
    users: Dict[int, User] = {}

    def __init__(self,
                 bot_mode="chat",
                 characters_dir_path="characters",
                 cutoff_mode="delete",
                 default_char_json="Example.json",
                 history_dir_path="extensions/telegram_bot/history",
                 default_token_file_path="extensions/telegram_bot/telegram_token.txt",
                 model_lang="en",
                 user_lang="en"
                 ):
        """
        Init telegram bot class. Use run_telegram_bot() to initiate bot.
        :param bot_mode: bot mode (chat, chat-restricted, notebook, persona). Default is "chat".
        :param characters_dir_path: place where stored characters .json files. Default is "chat".
        :param cutoff_mode: "cross" or "delete" message when "cutoff" button pressed
        :param default_char_json: name of default character.json file. Default is "chat".
        :param history_dir_path: place where stored chat history. Default is "extensions/telegram_bot/history".
        :param default_token_file_path: path to token file. Default is "extensions/telegram_bot/telegram_token.txt".
        :param model_lang: language of model
        :param user_lang: language of conversation
        :return: None
        """
        # Set paths to history, default token file, characters dir
        self.history_dir_path = history_dir_path
        self.default_token_file_path = default_token_file_path
        self.characters_dir_path = characters_dir_path
        # Set bot mode
        self.bot_mode = bot_mode
        # Set default character json file
        self.default_char_json = default_char_json
        # Set cutoff mode
        self.cutoff_mode = cutoff_mode
        # Bot message open/close html tags. Set ["", ""] to disable.
        self.html_tag = ["<pre>", "</pre>"]
        # Set translator
        self.model_lang = model_lang
        self.user_lang = user_lang
        # Set buttons
        self.keyboard_len = 12
        self.button_start = None
        if self.bot_mode == self.MODE_CHAT:
            self.button = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="▶Continue", callback_data=self.BTN_CONTINUE),
                        InlineKeyboardButton(
                            text="🔄Regenerate", callback_data=self.BTN_REGEN),
                        InlineKeyboardButton(
                            text="✂Cutoff", callback_data=self.BTN_CUTOFF),
                        InlineKeyboardButton(
                            text="🚫Reset", callback_data=self.BTN_RESET),
                        InlineKeyboardButton(
                            text="💾Download", callback_data=self.BTN_DOWNLOAD),
                        InlineKeyboardButton(
                            text="🎭Chars", callback_data=self.BTN_CHAR_LIST + "0"),
                    ]
                ]
            )
        elif self.bot_mode == self.MODE_CHAT_R:
            self.button = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="▶Continue", callback_data=self.BTN_CONTINUE),
                        InlineKeyboardButton(
                            text="🔄Regenerate", callback_data=self.BTN_REGEN),
                        InlineKeyboardButton(
                            text="✂Cutoff", callback_data=self.BTN_CUTOFF),
                        InlineKeyboardButton(
                            text="🚫Reset memory", callback_data=self.BTN_RESET),
                    ]
                ]
            )
        elif self.bot_mode == self.MODE_NOTEBOOK:
            self.button = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="▶Continue", callback_data=self.BTN_CONTINUE),
                        InlineKeyboardButton(
                            text="🚫Reset memory", callback_data=self.BTN_RESET),
                    ]
                ]
            )
        elif self.bot_mode == self.MODE_PERSONA:
            self.button = None
        # Set dummy obj for telegram updater
        self.updater = None
        # Define generator lock to prevent GPU overloading
        self.generator_lock = Lock()

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
            token_file_name = token_file_name or self.default_token_file_path
            with open(token_file_name, "r", encoding="utf-8") as f:
                bot_token = f.read().strip()

        self.updater = Updater(token=bot_token, use_context=True)
        self.updater.dispatcher.add_handler(
            CommandHandler("start", self.cb_start_command)),
        self.updater.dispatcher.add_handler(
            CommandHandler("reset", self.reset_history_button))
        self.updater.dispatcher.add_handler(
            CommandHandler("models", self.get_models))
        self.updater.dispatcher.add_handler(
            CommandHandler("chars", self.characters_keyboard_button))
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.text, self.cb_get_message))
        self.updater.dispatcher.add_handler(
            MessageHandler(Filters.document.mime_type("application/json"),
                           self.cb_get_json_document))
        self.updater.dispatcher.add_handler(
            CallbackQueryHandler(self.cb_opt_button))

        self.updater.start_polling()
        print("Telegram bot started!", self.updater)

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
        Thread(target=self.load_json_message, args=(upd, context)).start()

    # =============================================================================
    # Additional telegram actions
    def send_welcome_message(self, upd: Update, context: CallbackContext):
        chat_id = upd.effective_chat.id
        self.init_check_user(chat_id)
        send_text = self.message_template_generator("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text, chat_id=chat_id,
            reply_markup=self.button_start,
            parse_mode="HTML")

    def last_message_markup_clean(self, context: CallbackContext, chat_id: int):
        if (chat_id in self.users and
                len(self.users[chat_id].msg_id) > 0):
            last_msg = self.users[chat_id].msg_id[-1]
            try:
                context.bot.editMessageReplyMarkup(
                    chat_id=chat_id, message_id=last_msg,
                    reply_markup=None)
            except Exception as error:
                print("last_message_markup_clean", error)

    def message_template_generator(self, request: str, chat_id: int, custom_string="") -> str:
        # create a message using default_messages_template or return UNKNOWN_TEMPLATE
        if (request in self.default_messages_template and
                chat_id in self.users):
            msg = self.default_messages_template[request]
            msg = msg.replace("_CHAT_ID_", str(chat_id))
            msg = msg.replace("_NAME1_", self.users[chat_id].name1)
            msg = msg.replace("_NAME2_", self.users[chat_id].name2)
            msg = msg.replace("_CONTEXT_", self.users[chat_id].context)
            msg = msg.replace("_GREETING_", self.translate(self.users[chat_id].greeting, "to_user"))
            msg = msg.replace("_CUSTOM_STRING_", self.translate(custom_string, "to_user"))
            msg = msg.replace("_OPEN_TAG_", self.html_tag[0])
            msg = msg.replace("_CLOSE_TAG_", self.html_tag[1])
            return msg
        else:
            print(request, custom_string)
            return self.UNKNOWN_TEMPLATE

    # =============================================================================
    # Work with history! Init/load/save functions
    def parse_characters_dir(self) -> list:
        char_list = []
        for f in listdir(self.characters_dir_path):
            if f.endswith(('.json', '.yaml', '.yml')):
                char_list.append(f)
        return char_list

    def init_check_user(self, chat_id):
        if chat_id not in self.users:
            # Load default character
            self.users[chat_id] = self.load_character_file(
                char_file=self.default_char_json)
            # Load user history
            user_history_path = f'{self.history_dir_path}/{str(chat_id)}.json'
            user_char_history_path = f'{self.history_dir_path}/{str(chat_id)}{self.users[chat_id].name2}.json'
            if exists(user_history_path):
                self.load_user_history(chat_id, user_history_path)
            elif self.users[chat_id].name2 and exists(user_char_history_path):
                self.load_user_history(chat_id, user_char_history_path)

    def load_user_history(self, chat_id, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as user_file:
                data = user_file.read()
            self.users[chat_id].from_json(data)
        except Exception as error:
            print(f"load_user_history: {error}")

    def save_user_history(self, chat_id, chat_name=""):
        """
        Save two history file -user+char and default user history files and return their path
        :param chat_id: user chat_id
        :param chat_name: char name (or additional data)
        :return: user_char_file_path, default_user_file_path
        """
        if chat_id not in self.users:
            return None, None

        user_data = self.users[chat_id].to_json()
        user_char_file_path = Path(f"{self.history_dir_path}/{chat_id}{chat_name}.json")
        with user_char_file_path.open("w", encoding="utf-8") as user_file:
            user_file.write(user_data)

        default_user_file_path = Path(f"{self.history_dir_path}/{chat_id}.json")
        with default_user_file_path.open("w", encoding="utf-8") as user_file:
            user_file.write(user_data)

        return str(user_char_file_path), str(default_user_file_path)

    def load_json_message(self, upd: Update, context: CallbackContext):
        chat_id = upd.message.chat.id
        self.init_check_user(chat_id)
        default_user_file_path = str(Path(f'{self.history_dir_path}/{str(chat_id)}.json'))
        with open(default_user_file_path, 'wb') as f:
            context.bot.get_file(upd.message.document.file_id).download(out=f)

        self.load_user_history(chat_id, default_user_file_path)
        if len(self.users[chat_id].history) > 0:
            last_message = self.users[chat_id].history[-1]
        else:
            last_message = "<no message in history>"
        send_text = self.message_template_generator("hist_loaded", chat_id, last_message)
        context.bot.send_message(chat_id=chat_id, text=send_text,
                                 parse_mode="HTML")

    # =============================================================================
    # Message handler
    def load_character_command(self, upd: Update, context: CallbackContext):
        query = upd.callback_query
        char_list = self.parse_characters_dir()
        char_file = char_list[int(query.data.split(':')[1])]
        chat_id = query.message.chat_id
        self.users[chat_id] = self.load_character_file(char_file=char_file)
        #  If there was conversation with this char - load history
        user_char_history_path = f'{self.history_dir_path}/{str(chat_id)}{self.users[chat_id].name2}.json'
        if exists(user_char_history_path):
            self.load_user_history(chat_id, user_char_history_path)
        if len(self.users[chat_id].history) > 0:
            send_text = self.message_template_generator("hist_loaded", chat_id,
                                                        self.users[chat_id].history[-1])
        else:
            send_text = self.message_template_generator("char_loaded", chat_id)
        self.last_message_markup_clean(context, chat_id)
        context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
        context.bot.send_message(chat_id=chat_id, text=send_text, reply_markup=None, parse_mode="HTML")

    def model_button_click(self, upd: Update, context: CallbackContext):
        query = upd.callback_query
        model_list = server.get_available_models()
        model_file = model_list[int(query.data.split(':')[1])]
        try:
            context.bot.delete_message(chat_id=query.message.chat_id, message_id=query.message.message_id)
            message = context.bot.send_message(chat_id=upd.effective_chat.id, text="<b>Loading Model. 🪄</b>", parse_mode="HTML")
            server.unload_model()
            shared.model_name = model_file
            if model_file != '':
                shared.model, shared.tokenizer = server.load_model(shared.model_name)
            while server.load_model is None:
                time.sleep(1)
            context.bot.edit_message_text(chat_id=message.chat_id, message_id=message.message_id, text="<b>Model Loaded. ✅</b>", parse_mode="HTML")
        except Exception as e:
            print("model button error: ", e)
            context.bot.edit_message_text(chat_id=message.chat_id, message_id=message.message_id, text="<b>Error. ⛔</b>", parse_mode="HTML")

    def tr_get_message(self, upd: Update, context: CallbackContext):
        # Extract user input and chat ID
        user_text = upd.message.text
        chat_id = upd.message.chat.id
        self.init_check_user(chat_id)
        # Send "typing" message
        send_text = self.message_template_generator("typing", chat_id)
        message = context.bot.send_message(
            text=send_text, chat_id=chat_id,
            parse_mode="HTML")
        # Generate answer and replace "typing" message with it
        user_text = self.translate(user_text, "to_model")
        answer = self.generate_answer(user_in=user_text, chat_id=chat_id)
        answer = self.html_tag[0] + answer + self.html_tag[1]
        answer = self.translate(answer, "to_user")
        context.bot.editMessageText(
            text=answer, chat_id=chat_id,
            message_id=message.message_id,
            parse_mode="HTML",
            reply_markup=self.button)
        # Clear buttons on last message (if they exist in current thread)
        self.last_message_markup_clean(context, chat_id)
        # Add message ID to message history
        self.users[chat_id].msg_id.append(message.message_id)
        # Save user history
        self.save_user_history(chat_id, self.users[chat_id].name2)
        return True

    # =============================================================================
    # button
    def tr_opt_button(self, upd: Update, context: CallbackContext):
        query = upd.callback_query
        if query.data.startswith('CHARACTER_SELECTION:'):
            self.load_character_command(upd=upd, context=context)
        elif query.data.startswith('MODEL_SELECTION:'):
            self.model_button_click(upd=upd, context=context)
        else:
            query.answer()
            chat_id = query.message.chat.id
            msg_id = query.message.message_id
            msg_text = query.message.text
            option = query.data
            if chat_id not in self.users:
                self.init_check_user(chat_id)
            if msg_id not in self.users[chat_id].msg_id:
                send_text = msg_text + self.message_template_generator("mem_lost", chat_id)
                context.bot.editMessageText(
                    text=send_text, chat_id=chat_id,
                    message_id=msg_id,
                    reply_markup=None)
            else:
                self.handle_option(option, upd, context)
                self.save_user_history(chat_id, self.users[chat_id].name2)

    def handle_option(self, option, upd, context):
        if option == self.BTN_RESET:
            self.reset_history_button(upd=upd, context=context)
        elif option == self.BTN_CONTINUE:
            self.continue_message_button(upd=upd, context=context)
        elif option == self.BTN_REGEN:
            self.regenerate_message_button(upd=upd, context=context)
        elif option == self.BTN_CUTOFF:
            self.cutoff_message_button(upd=upd, context=context)
        elif option == self.BTN_DOWNLOAD:
            self.download_json_button(upd=upd, context=context)
        elif option.startswith(self.BTN_CHAR_LIST):
            self.characters_keyboard_button(upd=upd, context=context, option=option)
        elif option.startswith(self.BTN_CHAR_LOAD):
            self.load_character_button(upd=upd, context=context, option=option)

    def load_character_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        char_num = int(option.replace(self.BTN_CHAR_LOAD, ""))
        char_list = self.parse_characters_dir()
        self.last_message_markup_clean(context, chat_id)
        self.init_check_user(chat_id)
        char_file = char_list[char_num]
        self.users[chat_id] = self.load_character_file(char_file=char_file)
        #  If there was conversation with this char - load history
        user_char_history_path = f'{self.history_dir_path}/{str(chat_id)}{self.users[chat_id].name2}.json'
        if exists(user_char_history_path):
            self.load_user_history(chat_id, user_char_history_path)
        if len(self.users[chat_id].history) > 0:
            send_text = self.message_template_generator(
                "hist_loaded", chat_id, self.users[chat_id].history[-1])
        else:
            send_text = self.message_template_generator(
                "char_loaded", chat_id)
        context.bot.send_message(
            text=send_text, chat_id=chat_id,
            parse_mode="HTML")

    def characters_keyboard_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return char markup" button - clear markup
        if option == self.BTN_CHAR_LIST + "back":
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.button)
            return
        #  get keyboard list shift
        shift = int(option.replace(self.BTN_CHAR_LIST, ""))
        char_list = self.parse_characters_dir()
        if shift >= len(char_list):
            shift = 0
        #  create chars list
        characters_buttons = []
        for i in range(shift, self.keyboard_len + shift):
            if i >= len(char_list):
                break
            characters_buttons.append([InlineKeyboardButton(
                text=f"{char_list[i].replace('.json', '').replace('.yaml', '')}",
                callback_data=f"{self.BTN_CHAR_LOAD}{str(i)}"),
            ]
            )
        # add switch buttons
        switch_buttons = [
            InlineKeyboardButton(
                text="⏮",
                callback_data=self.BTN_CHAR_LIST + "0"),
            InlineKeyboardButton(
                text="⏪",
                callback_data=self.BTN_CHAR_LIST + str(shift - self.keyboard_len * 3)),
            InlineKeyboardButton(
                text="◀",
                callback_data=self.BTN_CHAR_LIST + str(shift - self.keyboard_len)),
            InlineKeyboardButton(
                text="⏹",
                callback_data=self.BTN_CHAR_LIST + "back"),
            InlineKeyboardButton(
                text="▶",
                callback_data=self.BTN_CHAR_LIST + str(shift + self.keyboard_len)),
            InlineKeyboardButton(
                text="⏩",
                callback_data=self.BTN_CHAR_LIST + str(shift + self.keyboard_len * 3)),
            InlineKeyboardButton(
                text="⏭",
                callback_data=self.BTN_CHAR_LIST + str(len(char_list) - self.keyboard_len)),
        ]
        characters_buttons.append(switch_buttons)
        # add new keyboard to message!
        characters_buttons = InlineKeyboardMarkup(characters_buttons)
        context.bot.editMessageReplyMarkup(
            chat_id=chat_id,
            message_id=msg.message_id,
            reply_markup=characters_buttons)
        
    def get_models(self, upd: Update, context: CallbackContext):
        model_list = server.get_available_models()
        keyboard = [[InlineKeyboardButton(item.replace('.json', '').replace('.yaml', ''), callback_data=f'MODEL_SELECTION:{index}')] for index, item in enumerate(model_list)]
        # Create an InlineKeyboardMarkup object with the list of buttons
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Send a message with the list of items and the keyboard
        if upd.callback_query:
            upd.callback_query.message.reply_text("<b>Select a model:</b>", reply_markup=reply_markup, parse_mode="HTML")
        else:
            context.bot.send_message(text="<b>Select a model:</b>", chat_id=upd.message.chat.id, reply_markup=reply_markup, parse_mode="HTML")

    def continue_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id

        # send "typing"
        self.last_message_markup_clean(context, chat_id)
        send_text = self.message_template_generator("typing", chat_id)
        message = context.bot.send_message(
            text=send_text, chat_id=chat_id,
            parse_mode="HTML")

        # get answer and replace message text!
        answer = self.generate_answer(user_in='', chat_id=chat_id)
        answer = self.html_tag[0] + answer + self.html_tag[1]
        answer = self.translate(answer, "to_user")
        context.bot.editMessageText(
            text=answer, chat_id=chat_id,
            message_id=message.message_id,
            reply_markup=self.button,
            parse_mode="HTML")
        self.users[chat_id].msg_id.append(message.message_id)

    def regenerate_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        user = self.users[chat_id]
        # add pretty "retyping" to message text
        send_text = self.html_tag[0] + msg.text + self.html_tag[1]
        send_text += self.message_template_generator('retyping', chat_id)
        context.bot.editMessageText(
            text=send_text, chat_id=chat_id,
            message_id=msg.message_id,
            parse_mode="HTML")

        # remove last bot answer, read and remove last user reply
        user_in, _ = user.pop()

        # get answer and replace message text!
        answer = self.generate_answer(user_in=user_in, chat_id=chat_id)
        answer = self.html_tag[0] + answer + self.html_tag[1]
        answer = self.translate(answer, "to_user")
        context.bot.editMessageText(
            text=answer, chat_id=chat_id,
            message_id=msg.message_id,
            reply_markup=self.button,
            parse_mode="HTML")
        user.msg_id.append(msg.message_id)

    def cutoff_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        user = self.users[chat_id]
        send_text = f"<s>{user.history[-1]}</s>"

        # Edit or delete last message ID (strict lines)
        last_msg_id = user.msg_id[-1]
        if self.cutoff_mode == self.CUTOFF_STRICT:
            context.bot.editMessageText(
                text=send_text, chat_id=chat_id,
                message_id=last_msg_id,
                parse_mode="HTML")
        else:
            context.bot.deleteMessage(
                chat_id=chat_id, message_id=last_msg_id)

        # Remove last message and bot answer from history
        user.pop()

        # If there is previous message - add buttons to previous message
        if user.msg_id:
            message_id = user.msg_id[-1]
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.button)
        self.save_user_history(chat_id, user.name2)

    def download_json_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id

        if chat_id not in self.users:
            return

        default_user_file_path, _ = self.save_user_history(chat_id)
        with open(default_user_file_path, 'r', encoding='utf-8') as default_user_file:
            send_caption = self.message_template_generator("hist_to_chat", chat_id)
            context.bot.send_document(
                chat_id=chat_id, caption=send_caption,
                document=default_user_file,
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
        context.bot.send_message(chat_id=chat_id, text=send_text, parse_mode="HTML")

    # =============================================================================
    # answer generator
    def generate_answer(self, user_in, chat_id):
        # if generation will fail, return "fail" answer
        answer = self.GENERATOR_FAIL
        user = self.users[chat_id]

        # Append user_in history
        user.user_in.append(user_in)

        # Preprocessing: add user_in to history in right order:
        if self.bot_mode == "notebook":
            # If notebook mode - append to history only user_in, no additional preparing;
            user.history.append(user_in)

        elif user_in.startswith(self.impersonate_prefix):
            # If user_in starts with prefix - impersonate-like (if you try to get "impersonate view")
            # adding "" line to prevent bug in history sequence, user_in is prefix for bot answer
            user.history.append("")
            user.history.append(user_in[len(self.impersonate_prefix):] + ":")

        elif user_in == "":
            # if user_in is "" - no user text, it is like continue generation
            # adding "" history line to prevent bug in history sequence, add "name2:" prefix for generation
            user.history.append("")
            user.history.append(user.name2 + ":")

        else:
            # If not notebook/impersonate/continue mode then ordinary chat preparing
            # add "name1&2:" to user and bot message (generation from name2 point of view);
            user.history.append(user.name1 + ":" + user_in)
            user.history.append(user.name2 + ":")

        # Set eos_token and stopping_strings.
        stopping_strings = []
        eos_token = None
        if self.bot_mode in ["chat", "chat-restricted"]:
            eos_token = '\n'

        # Make prompt: context + conversation history
        prompt = user.context + "\n".join(user.history).replace("\n\n", "\n")

        try:
            # acquire generator lock if we can
            self.generator_lock.acquire(timeout=600)
            # Generate!
            generator = generate_reply(question=prompt,
                                       state=self.generation_params,
                                       eos_token=eos_token,
                                       stopping_strings=stopping_strings)

            # This is "bad" implementation of getting answer, should be reworked
            for a in generator:
                answer = a

            # If generation result zero length - return  "Empty answer."
            if len(answer) < 1:
                answer = self.GENERATOR_EMPTY_ANSWER

        except Exception as error:
            print("generate_answer", error)

        finally:
            # anyway, release generator lock. Then return
            self.generator_lock.release()

            if answer not in [self.GENERATOR_EMPTY_ANSWER, self.GENERATOR_FAIL]:
                # if everything ok - add generated answer in history and return last message
                user.history[-1] = user.history[-1] + answer

            return user.history[-1]

    def translate(self, text, direction="to_user"):
        if self.model_lang != self.user_lang:
            if direction == "to_model":
                return GoogleTranslator(
                    source=self.user_lang,
                    target=self.model_lang).translate(text)
            elif direction == "to_user":
                return GoogleTranslator(
                    source=self.model_lang,
                    target=self.user_lang).translate(text)
        else:
            return text

    # =============================================================================
    # load characters char_file from ./characters
    def load_character_file(self, char_file: str):
        # Copy default user data. If reading will fail - return default user data
        user = self.User()
        try:
            # Try to read char file.
            char_file_path = Path(f'{self.characters_dir_path}/{char_file}')
            with open(char_file_path, 'r', encoding='utf-8') as user_file:
                if char_file.split(".")[-1] == "json":
                    data = json.loads(user_file.read())
                else:
                    data = yaml.safe_load(user_file.read())
            #  load persona and scenario
            if 'you_name' in data:
                user.name1 = data['you_name']
            if 'char_name' in data:
                user.name2 = data['char_name']
            if 'name' in data:
                user.name2 = data['name']
            if 'char_persona' in data:
                user.context += f"{data['char_name']}'s Persona: {data['char_persona'].strip()}\n"
            if 'world_scenario' in data:
                user.context += f"Scenario: {data['world_scenario'].strip()}\n"
            #  add dialogue examples
            if 'example_dialogue' in data:
                user.context += f"{data['example_dialogue'].strip()}\n"
            #  add <START>, add char greeting
            user.context += f"{user.context.strip()}\n<START>\n"
            if 'char_greeting' in data:
                user.context += '\n' + data['char_greeting'].strip()
                user.greeting = data['char_greeting'].strip()
            if 'greeting' in data:
                user.context += '\n' + data['greeting'].strip()
                user.greeting = data['greeting'].strip()
            user.context = self.replace_context_templates(user.context, user)
            user.greeting = self.replace_context_templates(user.greeting, user)
        except Exception as error:
            print("load_char_json_file", error)
        finally:
            return user

    @staticmethod
    def replace_context_templates(s: str, user: User) -> str:
        s = s.replace('{{char}}', user.name2)
        s = s.replace('{{user}}', user.name1)
        s = s.replace('<BOT>', user.name2)
        s = s.replace('<USER>', user.name1)
        return s


def run_server():
    # example with char load context:
    tg_server = TelegramBotWrapper(bot_mode=params['bot_mode'],
                                   default_char_json=params['character_to_load'],
                                   cutoff_mode=params["cutoff_mode"],
                                   user_lang=params["user_language"])
    # by default - read token from extensions/telegram_bot/telegram_token.txt
    tg_server.run_telegram_bot()


def setup():
    Thread(target=run_server, daemon=True).start()
