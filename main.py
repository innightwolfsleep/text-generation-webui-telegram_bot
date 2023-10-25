import io
import json
import logging
import os.path
import time
from pathlib import Path
from threading import Thread, Event
from typing import Dict, List

import backoff
import urllib3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAudio
from telegram.constants import CHATACTION_TYPING
from telegram.error import BadRequest, NetworkError
from telegram.ext import (
    CallbackContext,
    Filters,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
)
from telegram.ext import Updater


try:
    import extensions.telegram_bot.source.text_process as tp
    import extensions.telegram_bot.source.const as const
    import extensions.telegram_bot.source.utils as utils
    from extensions.telegram_bot.source.conf import cfg
    from extensions.telegram_bot.source.user import User as User
    from extensions.telegram_bot.source.extension.silero import Silero as Silero
    from extensions.telegram_bot.source.extension.sd_api import SdApi as SdApi
except ImportError:
    import source.text_process as tp
    import source.const as const
    import source.utils as utils
    from source.conf import cfg
    from source.user import User as User
    from source.extension.silero import Silero as Silero
    from source.extension.sd_api import SdApi as SdApi


class TelegramBotWrapper:
    # Set dummy obj for telegram updater
    updaters: List[Updater] = []

    # dict of User data dicts, here stored all users' session info.
    users: Dict[int, User] = {}

    def __init__(self, config_file_path="configs/app_config.json"):
        """Init telegram bot class. Use run_telegram_bot() to initiate bot.

        Args
            config_file_path: path to config file
        """
        logging.info(f"### TelegramBotWrapper INIT config_file_path: {config_file_path} ###")
        # Set&Load main config file
        self.config_file_path = config_file_path
        cfg.load(self.config_file_path)
        # Silero initiate
        self.silero = Silero()
        # SdApi initiate
        self.SdApi = SdApi(cfg.sd_api_url, cfg.sd_config_file_path)
        # Load user rules
        if os.path.exists(cfg.user_rules_file_path):
            with open(cfg.user_rules_file_path, "r") as user_rules_file:
                self.user_rules = json.loads(user_rules_file.read())
        else:
            logging.error("Cant find user_rules_file_path: " + cfg.user_rules_file_path)
            self.user_rules = {}
        # initiate generator
        tp.init(
            cfg.generator_script,
            cfg.model_path,
            n_ctx=cfg.generation_params.get("chat_prompt_size", 1024),
            n_gpu_layers=cfg.generation_params.get("n_gpu_layers", 0),
        )
        logging.info(f"### TelegramBotWrapper INIT DONE ###")
        logging.info(f"### !!! READY !!! ###")

    # =============================================================================
    # Run bot with token! Initiate updater obj!
    def run_telegram_bot(self, bot_token="", token_file_name=""):
        """
        Start the Telegram bot.
        :param bot_token: (str) The Telegram bot tokens separated by ','
                                If not provided, try to read it from `token_file_name`.
        :param token_file_name: (str) The name of the file containing the bot token. Default is `None`.
        :return: None
        """
        request_kwargs = {
            "proxy_url": cfg.proxy_url,
        }
        if not bot_token:
            token_file_name = token_file_name or cfg.token_file_path
            with open(token_file_name, "r", encoding="utf-8") as f:
                bot_token = f.read().strip()
        for token in bot_token.split(","):
            updater = Updater(token=token, use_context=True, request_kwargs=request_kwargs)
            updater.dispatcher.add_handler(CommandHandler("start", self.cb_start_command)),
            updater.dispatcher.add_handler(MessageHandler(Filters.text, self.cb_get_message))
            doc = "application/json"
            updater.dispatcher.add_handler(
                MessageHandler(
                    Filters.document.mime_type(doc),
                    self.cb_get_json_document,
                )
            )
            updater.dispatcher.add_handler(CallbackQueryHandler(self.cb_opt_button))
            updater.start_polling()
            logging.info("Telegram bot started!" + str(updater))
            self.updaters.append(updater)
            logging.info(f"### TelegramBotWrapper run_telegram_bot {str(updater)} DONE ###")
        Thread(target=self.no_sleep_callback).start()

    def no_sleep_callback(self):
        while True:
            for updater in self.updaters:
                try:
                    updater.bot.send_message(chat_id=99999999999, text="One message every minute")
                except BadRequest:
                    pass
                except Exception as error:
                    logging.error(error)
            time.sleep(60)

    # =============================================================================
    # Handlers
    def cb_start_command(self, upd, context):
        Thread(target=self.thread_welcome_message, args=(upd, context)).start()

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
        if not utils.check_user_permission(chat_id):
            return False
        utils.init_check_user(self.users, chat_id)
        send_text = self.make_template_message("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
            parse_mode="HTML",
        )

    @staticmethod
    def get_user_profile_name(upd: Update) -> str:
        message = upd.message or upd.callback_query.message
        user_name = cfg.user_name_template.replace("FIRSTNAME", message.from_user.first_name or "")
        user_name = user_name.replace("LASTNAME", message.from_user.last_name or "")
        user_name = user_name.replace("USERNAME", message.from_user.username or "")
        user_name = user_name.replace("ID", str(message.from_user.id) or "")
        return user_name

    def make_template_message(self, request: str, chat_id: int, custom_string="") -> str:
        # create a message using default_messages_template or return
        # UNKNOWN_TEMPLATE
        if chat_id in self.users:
            user = self.users[chat_id]
            if request in const.DEFAULT_MESSAGE_TEMPLATE:
                msg = const.DEFAULT_MESSAGE_TEMPLATE[request]
                msg = msg.replace("_CHAT_ID_", str(chat_id))
                msg = msg.replace("_NAME1_", user.name1)
                msg = msg.replace("_NAME2_", user.name2)
                msg = msg.replace("_CONTEXT_", user.context)
                msg = msg.replace(
                    "_GREETING_",
                    utils.prepare_text(user.greeting, user, "to_user"),
                )
                msg = msg.replace(
                    "_CUSTOM_STRING_",
                    utils.prepare_text(custom_string, user, "to_user"),
                )
                msg = msg.replace("_OPEN_TAG_", cfg.html_tag[0])
                msg = msg.replace("_CLOSE_TAG_", cfg.html_tag[1])
                return msg
            else:
                return const.UNKNOWN_TEMPLATE
        else:
            return const.UNKNOWN_USER

    # =============================================================================
    # Work with history! Init/load/save functions

    def thread_get_json_document(self, upd: Update, context: CallbackContext):
        chat_id = upd.message.chat.id
        user = self.users[chat_id]
        if not utils.check_user_permission(chat_id):
            return False
        utils.init_check_user(self.users, chat_id)
        default_user_file_path = str(Path(f"{cfg.history_dir_path}/{str(chat_id)}.json"))
        with open(default_user_file_path, "wb") as f:
            context.bot.get_file(upd.message.document.file_id).download(out=f)
        user.load_user_history(default_user_file_path)
        if len(user.history) > 0:
            last_message = user.history[-1]["out"]
        else:
            last_message = "<no message in history>"
        send_text = self.make_template_message("hist_loaded", chat_id, last_message)
        context.bot.send_message(
            chat_id=chat_id,
            text=send_text,
            reply_markup=self.get_options_keyboard(chat_id, user),
            parse_mode="HTML",
        )

    def start_send_typing_status(self, context: CallbackContext, chat_id: int) -> Event:
        typing_active = Event()
        typing_active.set()
        Thread(target=self.thread_typing_status, args=(context, chat_id, typing_active)).start()
        return typing_active

    @staticmethod
    def thread_typing_status(context: CallbackContext, chat_id: int, typing_active: Event):
        limit_counter = int(cfg.generation_timeout / 5)
        while typing_active.is_set() and limit_counter > 0:
            context.bot.send_chat_action(chat_id=chat_id, action=CHATACTION_TYPING)
            time.sleep(5)
            limit_counter -= 1

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def send_sd_image(self, upd: Update, context: CallbackContext, answer: str, user_text: str):
        chat_id = upd.message.chat.id
        try:
            file_list = self.SdApi.txt_to_image(answer)
            answer = answer.replace(cfg.sd_api_prompt_of.replace("OBJECT", user_text[1:].strip()), "")
            for char in ["[", "]", "{", "}", "(", ")", "*", '"', "'"]:
                answer = answer.replace(char, "")
            if len(answer) > 1023:
                answer = answer[:1023]
            if len(file_list) > 0:
                for image_path in file_list:
                    if os.path.exists(image_path):
                        with open(image_path, "rb") as image_file:
                            context.bot.send_photo(caption=answer, chat_id=chat_id, photo=image_file)
                        os.remove(image_path)
        except Exception as e:
            logging.error("send_sd_image: " + str(e))
            context.bot.send_message(text=answer, chat_id=chat_id)

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def clean_last_message_markup(self, context: CallbackContext, chat_id: int):
        if chat_id in self.users and len(self.users[chat_id].msg_id) > 0:
            last_msg = self.users[chat_id].msg_id[-1]
            try:
                context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=last_msg)
            except Exception as exception:
                logging.info("last_message_markup_clean: " + str(exception))

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def send_message(self, context: CallbackContext, chat_id: int, text: str):
        user = self.users[chat_id]
        text = utils.prepare_text(text, user, "to_user")
        if user.silero_speaker == "None" or user.silero_model_id == "None":
            message = context.bot.send_message(
                text=text,
                chat_id=chat_id,
                parse_mode="HTML",
                reply_markup=self.get_chat_keyboard(),
            )
            return message
        else:
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                with open(audio_path, "rb") as audio:
                    message = context.bot.send_audio(
                        chat_id=chat_id,
                        audio=audio,
                        caption=text,
                        filename=f"{user.name2}_to_{user.name1}.wav",
                        parse_mode="HTML",
                        reply_markup=self.get_chat_keyboard(),
                    )
            else:
                message = context.bot.send_message(
                    text=text,
                    chat_id=chat_id,
                    parse_mode="HTML",
                    reply_markup=self.get_chat_keyboard(),
                )
                return message
            return message

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError, NetworkError),
        max_time=60,
    )
    def edit_message(
        self,
        context: CallbackContext,
        upd: Update,
        chat_id: int,
        text: str,
        message_id: int,
    ):
        user = self.users[chat_id]
        text = utils.prepare_text(text, user, "to_user")
        if upd.callback_query.message.text is not None:
            context.bot.editMessageText(
                text=text,
                chat_id=chat_id,
                parse_mode="HTML",
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(),
            )
        if (
            upd.callback_query.message.audio is not None
            and user.silero_speaker != "None"
            and user.silero_model_id != "None"
        ):
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                with open(audio_path, "rb") as audio:
                    media = InputMediaAudio(media=audio, filename=f"{user.name2}_to_{user.name1}.wav")
                    context.bot.edit_message_media(
                        chat_id=chat_id,
                        media=media,
                        message_id=message_id,
                        reply_markup=self.get_chat_keyboard(),
                    )
        if upd.callback_query.message.caption is not None:
            context.bot.editMessageCaption(
                chat_id=chat_id,
                caption=text,
                parse_mode="HTML",
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(),
            )

    # =============================================================================
    # Message handler
    def thread_get_message(self, upd: Update, context: CallbackContext):
        # Extract user input and chat ID
        user_text = upd.message.text
        chat_id = upd.message.chat.id
        utils.init_check_user(self.users, chat_id)
        user = self.users[chat_id]
        if not utils.check_user_permission(chat_id):
            return False
        if not user.check_flooding(cfg.flood_avoid_delay):
            return False
        # Send "typing" message
        typing = self.start_send_typing_status(context, chat_id)
        try:
            if utils.check_user_rule(chat_id=chat_id, option=const.GET_MESSAGE) is not True:
                return False
            # Generate answer and replace "typing" message with it
            if not user_text.startswith(tuple(cfg.sd_api_prefixes)):
                user_text = utils.prepare_text(user_text, user, "to_model")
            answer, system_message = tp.get_answer(
                text_in=user_text,
                user=user,
                bot_mode=cfg.bot_mode,
                generation_params=cfg.generation_params,
                name_in=self.get_user_profile_name(upd),
            )
            if system_message == const.MSG_SYSTEM:
                context.bot.send_message(text=answer, chat_id=chat_id)
            elif system_message == const.MSG_SD_API:
                user.truncate_last_message()
                self.send_sd_image(upd, context, answer, user_text)
            else:
                if system_message == const.MSG_DEL_LAST:
                    context.bot.deleteMessage(chat_id=chat_id, message_id=user.msg_id[-1])
                message = self.send_message(text=answer, chat_id=chat_id, context=context)
                # Clear buttons on last message (if they exist in current
                # thread)
                self.clean_last_message_markup(context, chat_id)
                # Add message ID to message history
                user.msg_id.append(message.message_id)
                # Save user history
                user.save_user_history(chat_id, cfg.history_dir_path)
        except Exception as e:
            logging.error(str(e))
        finally:
            typing.clear()

    # =============================================================================
    # button
    def thread_push_button(self, upd: Update, context: CallbackContext):
        upd.callback_query.answer()
        chat_id = upd.callback_query.message.chat.id
        msg_id = upd.callback_query.message.message_id
        option = upd.callback_query.data
        if not utils.check_user_permission(chat_id):
            return False
        # Send "typing" message
        typing = self.start_send_typing_status(context, chat_id)
        try:
            # if new user - init
            utils.init_check_user(self.users, chat_id)
            # if button - is chat-interactive button need to check msg consistency
            if option in [
                const.BTN_IMPERSONATE,
                const.BTN_NEXT,
                const.BTN_CONTINUE,
                const.BTN_DEL_WORD,
                const.BTN_REGEN,
                const.BTN_CUTOFF,
            ]:
                # if lost message button - clear markup and return
                if len(self.users[chat_id].msg_id) == 0:
                    context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
                    return
                else:
                    # if msg list not empty but  lost button - clear markup and return
                    if msg_id != self.users[chat_id].msg_id[-1]:
                        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg_id, reply_markup=None)
                        return
            self.handle_button_option(option, chat_id, upd, context)
            self.users[chat_id].save_user_history(chat_id, cfg.history_dir_path)
        except Exception as e:
            logging.error("thread_push_button " + str(e) + str(e.args))
        finally:
            typing.clear()

    def handle_button_option(self, option, chat_id, upd, context):
        if option == const.BTN_RESET and utils.check_user_rule(chat_id, option):
            self.on_reset_history_button(upd=upd, context=context)
        elif option == const.BTN_CONTINUE and utils.check_user_rule(chat_id, option):
            self.on_continue_message_button(upd=upd, context=context)
        elif option == const.BTN_IMPERSONATE and utils.check_user_rule(chat_id, option):
            self.on_impersonate_button(upd=upd, context=context)
        elif option == const.BTN_NEXT and utils.check_user_rule(chat_id, option):
            self.on_next_message_button(upd=upd, context=context)
        elif option == const.BTN_DEL_WORD and utils.check_user_rule(chat_id, option):
            self.on_delete_word_button(upd=upd, context=context)
        elif option == const.BTN_REGEN and utils.check_user_rule(chat_id, option):
            self.on_regenerate_message_button(upd=upd, context=context)
        elif option == const.BTN_CUTOFF and utils.check_user_rule(chat_id, option):
            self.on_cutoff_message_button(upd=upd, context=context)
        elif option == const.BTN_DOWNLOAD and utils.check_user_rule(chat_id, option):
            self.on_download_json_button(upd=upd, context=context)
        elif option == const.BTN_OPTION and utils.check_user_rule(chat_id, option):
            self.show_options_button(upd=upd, context=context)
        elif option == const.BTN_DELETE and utils.check_user_rule(chat_id, option):
            self.on_delete_pressed_button(upd=upd, context=context)
        elif option.startswith(const.BTN_CHAR_LIST) and utils.check_user_rule(chat_id, option):
            self.keyboard_characters_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_CHAR_LOAD) and utils.check_user_rule(chat_id, option):
            self.load_character_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_PRESET_LIST) and utils.check_user_rule(chat_id, option):
            self.keyboard_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_PRESET_LOAD) and utils.check_user_rule(chat_id, option):
            self.load_presets_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_MODEL_LIST) and utils.check_user_rule(chat_id, option):
            self.on_keyboard_models_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_MODEL_LOAD) and utils.check_user_rule(chat_id, option):
            self.on_load_model_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_LANG_LIST) and utils.check_user_rule(chat_id, option):
            self.on_keyboard_language_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_LANG_LOAD) and utils.check_user_rule(chat_id, option):
            self.on_load_language_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_VOICE_LIST) and utils.check_user_rule(chat_id, option):
            self.on_keyboard_voice_button(upd=upd, context=context, option=option)
        elif option.startswith(const.BTN_VOICE_LOAD) and utils.check_user_rule(chat_id, option):
            self.on_load_voice_button(upd=upd, context=context, option=option)

    def show_options_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        send_text = self.get_conversation_info(user)
        context.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id, user),
            parse_mode="HTML",
        )

    @staticmethod
    def on_delete_pressed_button(upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        message_id = upd.callback_query.message.message_id
        context.bot.deleteMessage(chat_id=chat_id, message_id=message_id)

    def on_impersonate_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        self.clean_last_message_markup(context, chat_id)
        answer, _ = tp.get_answer(
            text_in=const.GENERATOR_MODE_IMPERSONATE,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(upd),
        )
        message = self.send_message(text=answer, chat_id=chat_id, context=context)
        user.msg_id.append(message.message_id)
        user.save_user_history(chat_id, cfg.history_dir_path)

    def on_next_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        self.clean_last_message_markup(context, chat_id)
        answer, _ = tp.get_answer(
            text_in=const.GENERATOR_MODE_NEXT,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(upd),
        )
        message = self.send_message(text=answer, chat_id=chat_id, context=context)
        user.msg_id.append(message.message_id)
        user.save_user_history(chat_id, cfg.history_dir_path)

    def on_continue_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        message = upd.callback_query.message
        user = self.users[chat_id]
        # get answer and replace message text!
        answer, _ = tp.get_answer(
            text_in=const.GENERATOR_MODE_CONTINUE,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(upd),
        )
        self.edit_message(
            text=answer,
            chat_id=chat_id,
            message_id=message.message_id,
            context=context,
            upd=upd,
        )
        user.change_last_message(history_answer=answer)
        user.save_user_history(chat_id, cfg.history_dir_path)

    def on_delete_word_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        answer, return_msg_action = tp.get_answer(
            text_in=const.GENERATOR_MODE_DEL_WORD,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(upd),
        )
        if return_msg_action != const.MSG_NOTHING_TO_DO:
            self.edit_message(
                text=answer,
                chat_id=chat_id,
                message_id=user.msg_id[-1],
                context=context,
                upd=upd,
            )
            user.save_user_history(chat_id, cfg.history_dir_path)

    def on_regenerate_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        user = self.users[chat_id]
        self.clean_last_message_markup(context, chat_id)
        # get answer and replace message text!
        answer, _ = tp.get_answer(
            text_in=const.GENERATOR_MODE_REGENERATE,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(upd),
        )
        self.edit_message(
            text=answer,
            chat_id=chat_id,
            message_id=msg.message_id,
            context=context,
            upd=upd,
        )
        user.save_user_history(chat_id, cfg.history_dir_path)

    def on_cutoff_message_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        # Edit or delete last message ID (strict lines)
        last_msg_id = user.msg_id[-1]
        context.bot.deleteMessage(chat_id=chat_id, message_id=last_msg_id)
        # Remove last message and bot answer from history
        user.truncate_last_message()
        # If there is previous message - add buttons to previous message
        if user.msg_id:
            message_id = user.msg_id[-1]
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(),
            )
        user.save_user_history(chat_id, cfg.history_dir_path)

    def on_download_json_button(self, upd: Update, context: CallbackContext):
        chat_id = upd.callback_query.message.chat.id

        if chat_id not in self.users:
            return

        user_file = io.StringIO(self.users[chat_id].to_json())
        send_caption = self.make_template_message("hist_to_chat", chat_id)
        context.bot.send_document(
            chat_id=chat_id,
            caption=send_caption,
            document=user_file,
            filename=self.users[chat_id].name2 + ".json",
        )

    def on_reset_history_button(self, upd: Update, context: CallbackContext):
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
        user.reset()
        user.load_character_file(cfg.characters_dir_path, user.char_file)
        send_text = self.make_template_message("mem_reset", chat_id)
        context.bot.send_message(
            chat_id=chat_id,
            text=send_text,
            reply_markup=self.get_options_keyboard(chat_id, user),
            parse_mode="HTML",
        )

    # =============================================================================
    # switching keyboard
    def on_load_model_button(self, upd: Update, context: CallbackContext, option: str):
        if tp.get_model_list is not None:
            model_list = tp.get_model_list()
            model_file = model_list[int(option.replace(const.BTN_MODEL_LOAD, ""))]
            chat_id = upd.effective_chat.id
            send_text = "Loading " + model_file + ". 🪄"
            message_id = upd.callback_query.message.message_id
            context.bot.editMessageText(
                text=send_text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
            )
            try:
                tp.load_model(model_file)
                send_text = self.make_template_message(
                    request="model_loaded", chat_id=chat_id, custom_string=model_file
                )
                context.bot.editMessageText(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=send_text,
                    parse_mode="HTML",
                    reply_markup=self.get_options_keyboard(
                        chat_id, self.users[chat_id] if chat_id in self.users else None
                    ),
                )
            except Exception as e:
                logging.error("model button error: " + str(e))
                context.bot.editMessageText(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Error during " + model_file + " loading. ⛔",
                    parse_mode="HTML",
                    reply_markup=self.get_options_keyboard(
                        chat_id, self.users[chat_id] if chat_id in self.users else None
                    ),
                )
                raise e

    def on_keyboard_models_button(self, upd: Update, context: CallbackContext, option: str):
        if tp.get_model_list() is not None:
            chat_id = upd.callback_query.message.chat.id
            msg = upd.callback_query.message
            model_list = tp.get_model_list()
            if option == const.BTN_MODEL_LIST + const.BTN_OPTION:
                context.bot.editMessageReplyMarkup(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    reply_markup=self.get_options_keyboard(
                        chat_id, self.users[chat_id] if chat_id in self.users else None
                    ),
                )
                return
            shift = int(option.replace(const.BTN_MODEL_LIST, ""))
            characters_buttons = self.get_switch_keyboard(
                opt_list=model_list,
                shift=shift,
                data_list=const.BTN_MODEL_LIST,
                data_load=const.BTN_MODEL_LOAD,
            )
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=characters_buttons,
            )

    def load_presets_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        preset_char_num = int(option.replace(const.BTN_PRESET_LOAD, ""))
        cfg.preset_file = utils.parse_presets_dir()[preset_char_num]
        cfg.load_preset(preset_file=cfg.preset_file)
        user = self.users[chat_id]
        send_text = self.get_conversation_info(user)
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id, user),
        )

    def keyboard_presets_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_PRESET_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_PRESET_LIST, ""))
        preset_list = utils.parse_presets_dir()
        characters_buttons = self.get_switch_keyboard(
            opt_list=preset_list,
            shift=shift,
            data_list=const.BTN_PRESET_LIST,
            data_load=const.BTN_PRESET_LOAD,
            keyboard_column=3,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=characters_buttons)

    def load_character_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        char_num = int(option.replace(const.BTN_CHAR_LOAD, ""))
        char_list = utils.parse_characters_dir()
        self.clean_last_message_markup(context, chat_id)
        utils.init_check_user(self.users, chat_id)
        char_file = char_list[char_num]
        self.users[chat_id].load_character_file(characters_dir_path=cfg.characters_dir_path, char_file=char_file)
        #  If there was conversation with this character_file - load history
        self.users[chat_id].find_and_load_user_char_history(chat_id, cfg.history_dir_path)
        if len(self.users[chat_id].history) > 0:
            send_text = self.make_template_message("hist_loaded", chat_id, self.users[chat_id].history[-1]["out"])
        else:
            send_text = self.make_template_message("char_loaded", chat_id)
        context.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
        )

    def keyboard_characters_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_CHAR_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_CHAR_LIST, ""))
        char_list = utils.parse_characters_dir()
        if shift == -9999 and self.users[chat_id].char_file in char_list:
            shift = char_list.index(self.users[chat_id].char_file)
        #  create chars list
        characters_buttons = self.get_switch_keyboard(
            opt_list=char_list,
            shift=shift,
            data_list=const.BTN_CHAR_LIST,
            data_load=const.BTN_CHAR_LOAD,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=characters_buttons)

    def on_load_language_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        lang_num = int(option.replace(const.BTN_LANG_LOAD, ""))
        language = list(cfg.language_dict.keys())[lang_num]
        self.users[chat_id].language = language
        send_text = self.get_conversation_info(user)
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id, user),
        )

    def on_keyboard_language_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_LANG_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_LANG_LIST, ""))
        #  create list
        lang_buttons = self.get_switch_keyboard(
            opt_list=list(cfg.language_dict.keys()),
            shift=shift,
            data_list=const.BTN_LANG_LIST,
            data_load=const.BTN_LANG_LOAD,
            keyboard_column=4,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=lang_buttons)

    @staticmethod
    def get_conversation_info(user: User):
        history_tokens = -1
        context_tokens = -1
        greeting_tokens = -1
        conversation_tokens = -1
        try:
            history_tokens = tp.get_tokens_count(user.history_as_str())
            context_tokens = tp.get_tokens_count(user.context)
            greeting_tokens = tp.get_tokens_count(user.greeting)
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

    def on_load_voice_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        user = self.users[chat_id]
        male = Silero.voices[user.language]["male"]
        female = Silero.voices[user.language]["female"]
        voice_dict = ["None"] + male + female
        voice_num = int(option.replace(const.BTN_VOICE_LOAD, ""))
        user.silero_speaker = voice_dict[voice_num]
        user.silero_model_id = Silero.voices[user.language]["model"]
        send_text = self.get_conversation_info(user)
        message_id = upd.callback_query.message.message_id
        context.bot.editMessageText(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id, user),
        )

    def on_keyboard_voice_button(self, upd: Update, context: CallbackContext, option: str):
        chat_id = upd.callback_query.message.chat.id
        msg = upd.callback_query.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_VOICE_LIST + const.BTN_OPTION:
            context.bot.editMessageReplyMarkup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=self.get_options_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
            )
            return
        #  get keyboard list shift
        shift = int(option.replace(const.BTN_VOICE_LIST, ""))
        #  create list
        user = self.users[chat_id]
        male = list(map(lambda x: x + "🚹", Silero.voices[user.language]["male"]))
        female = list(map(lambda x: x + "🚺", Silero.voices[user.language]["female"]))
        voice_dict = ["🔇None"] + male + female
        voice_buttons = self.get_switch_keyboard(
            opt_list=list(voice_dict),
            shift=shift,
            data_list=const.BTN_VOICE_LIST,
            data_load=const.BTN_VOICE_LOAD,
            keyboard_column=4,
        )
        context.bot.editMessageReplyMarkup(chat_id=chat_id, message_id=msg.message_id, reply_markup=voice_buttons)

    # =============================================================================
    # load characters char_file from ./characters
    @staticmethod
    def get_options_keyboard(chat_id, user: User):
        keyboard_raw = []
        # get language
        if user is not None:
            language = user.language
        else:
            language = "en"
        language_flag = cfg.language_dict[language]
        # get voice
        if user is not None:
            voice_str = user.silero_speaker
        else:
            voice_str = "None"
        if voice_str == "None":
            voice = "🔇"
        else:
            voice = "🔈"

        if utils.check_user_rule(chat_id, const.BTN_DOWNLOAD):
            keyboard_raw.append(InlineKeyboardButton(text="💾Save", callback_data=const.BTN_DOWNLOAD))
        # if utils.check_user_rule(chat_id, const.BTN_LORE):
        #    keyboard_raw.append(InlineKeyboardButton(
        #        text="📜Lore", callback_data=const.BTN_LORE))
        if utils.check_user_rule(chat_id, const.BTN_CHAR_LIST):
            keyboard_raw.append(InlineKeyboardButton(text="🎭Chars", callback_data=const.BTN_CHAR_LIST + "-9999"))
        if utils.check_user_rule(chat_id, const.BTN_RESET):
            keyboard_raw.append(InlineKeyboardButton(text="⚠Reset", callback_data=const.BTN_RESET))
        if utils.check_user_rule(chat_id, const.BTN_LANG_LIST):
            keyboard_raw.append(
                InlineKeyboardButton(
                    text=language_flag + "Language",
                    callback_data=const.BTN_LANG_LIST + "0",
                )
            )
        if utils.check_user_rule(chat_id, const.BTN_VOICE_LIST):
            keyboard_raw.append(InlineKeyboardButton(text=voice + "Voice", callback_data=const.BTN_VOICE_LIST + "0"))
        if utils.check_user_rule(chat_id, const.BTN_PRESET_LIST) and tp.generator.preset_change_allowed:
            keyboard_raw.append(InlineKeyboardButton(text="🔧Presets", callback_data=const.BTN_PRESET_LIST + "0"))
        if utils.check_user_rule(chat_id, const.BTN_MODEL_LIST) and tp.generator.model_change_allowed:
            keyboard_raw.append(InlineKeyboardButton(text="🔨Model", callback_data=const.BTN_MODEL_LIST + "0"))
        if utils.check_user_rule(chat_id, const.BTN_DELETE):
            keyboard_raw.append(InlineKeyboardButton(text="❌Close", callback_data=const.BTN_DELETE))
        return InlineKeyboardMarkup([keyboard_raw])

    @staticmethod
    def get_chat_keyboard(chat_id=0):
        keyboard_raw = []
        if utils.check_user_rule(chat_id, const.BTN_IMPERSONATE):
            keyboard_raw.append(InlineKeyboardButton(text="🥸Impersonate", callback_data=const.BTN_IMPERSONATE))
        if utils.check_user_rule(chat_id, const.BTN_NEXT):
            keyboard_raw.append(InlineKeyboardButton(text="▶Next", callback_data=const.BTN_NEXT))
        if utils.check_user_rule(chat_id, const.BTN_CONTINUE):
            keyboard_raw.append(InlineKeyboardButton(text="➡Continue", callback_data=const.BTN_CONTINUE))
        if utils.check_user_rule(chat_id, const.BTN_DEL_WORD):
            keyboard_raw.append(InlineKeyboardButton(text="⬅Del sentence", callback_data=const.BTN_DEL_WORD))
        if utils.check_user_rule(chat_id, const.BTN_REGEN):
            keyboard_raw.append(InlineKeyboardButton(text="♻Regenerate", callback_data=const.BTN_REGEN))
        if utils.check_user_rule(chat_id, const.BTN_CUTOFF):
            keyboard_raw.append(InlineKeyboardButton(text="✂️Cutoff", callback_data=const.BTN_CUTOFF))
        if utils.check_user_rule(chat_id, const.BTN_OPTION):
            keyboard_raw.append(InlineKeyboardButton(text="⚙Options", callback_data=const.BTN_OPTION))
        return InlineKeyboardMarkup([keyboard_raw])

    @staticmethod
    def get_switch_keyboard(
        opt_list: list,
        shift: int,
        data_list: str,
        data_load: str,
        keyboard_rows=6,
        keyboard_column=2,
    ):
        # find shift
        opt_list_length = len(opt_list)
        keyboard_length = keyboard_rows * keyboard_column
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
            if column >= keyboard_column:
                column = 0
            characters_buttons[-1].append(
                InlineKeyboardButton(text=f"{opt_list[i]}", callback_data=f"{data_load}{str(i)}")
            )
            i += 1
        # add switch buttons
        ordinary_shift = keyboard_length
        improved_shift = (
            int(opt_list_length / 8) if opt_list_length / (keyboard_length * 3) > 8 else keyboard_length * 3
        )
        begin_shift = 0
        l_shift = shift - ordinary_shift
        l_shift3 = shift - improved_shift
        r_shift = shift + ordinary_shift
        r_shift3 = shift + improved_shift
        end_shift = opt_list_length - keyboard_length
        switch_buttons = [
            InlineKeyboardButton(text="⏮", callback_data=data_list + str(begin_shift)),
            InlineKeyboardButton(text="⏪", callback_data=data_list + str(l_shift3)),
            InlineKeyboardButton(text="◀", callback_data=data_list + str(l_shift)),
            InlineKeyboardButton(text="🔺", callback_data=data_list + const.BTN_OPTION),
            InlineKeyboardButton(text="▶", callback_data=data_list + str(r_shift)),
            InlineKeyboardButton(text="⏩", callback_data=data_list + str(r_shift3)),
            InlineKeyboardButton(text="⏭", callback_data=data_list + str(end_shift)),
        ]
        characters_buttons.append(switch_buttons)
        # add new keyboard to message!
        return InlineKeyboardMarkup(characters_buttons)
