import json
import io
import logging
import asyncio
from os.path import exists, normpath
from os import remove
from pathlib import Path
from threading import Event
from typing import Dict, Union

import backoff
import urllib3
from aiogram import Bot, types
from aiogram.types import Message, CallbackQuery
from aiogram.types.inline_keyboard import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher.dispatcher import Dispatcher
from aiogram.types.input_file import InputFile
from aiogram.types.input_media import InputMediaAudio


logging.basicConfig(level=logging.INFO)


try:
    import extensions.telegram_bot.source.text_process as tp
    import extensions.telegram_bot.source.const as const
    import extensions.telegram_bot.source.utils as utils
    import extensions.telegram_bot.source.buttons as buttons
    from extensions.telegram_bot.source.conf import cfg
    from extensions.telegram_bot.source.user import User as User
    from extensions.telegram_bot.source.extension.silero import Silero as Silero
    from extensions.telegram_bot.source.extension.sd_api import SdApi as SdApi
except ImportError:
    import source.text_process as tp
    import source.const as const
    import source.utils as utils
    import source.buttons as buttons
    from source.conf import cfg
    from source.user import User as User
    from source.extension.silero import Silero as Silero
    from source.extension.sd_api import SdApi as SdApi


class AiogramLlmBot:
    # Set dummy obj for telegram updater
    bot: Union[Bot, None] = None
    dp: Union[Dispatcher, None] = None
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
        if exists(cfg.user_rules_file_path):
            with open(normpath(cfg.user_rules_file_path), "r") as user_rules_file:
                self.user_rules = json.loads(user_rules_file.read())
        else:
            logging.error("Cant find user_rules_file_path: " + cfg.user_rules_file_path)
            self.user_rules = {}
        # initiate generator
        tp.generator.init(
            cfg.generator_script,
            cfg.llm_path,
            n_ctx=cfg.generation_params.get("chat_prompt_size", 1024),
            n_gpu_layers=cfg.generation_params.get("n_gpu_layers", 0),
        )
        logging.info(f"### TelegramBotWrapper INIT DONE ###")
        logging.info(f"### !!! READY !!! ###")

    # =============================================================================
    # Run bot with token! Initiate updater obj!
    async def run_telegram_bot(self, bot_token="", token_file_name=""):
        """
        Start the Telegram bot.
        :param bot_token: (str) The Telegram bot tokens separated by ','
                                If not provided, try to read it from `token_file_name`.
        :param token_file_name: (str) The name of the file containing the bot token. Default is `None`.
        :return: None
        """
        if not bot_token:
            token_file_name = token_file_name or cfg.token_file_path
            with open(normpath(token_file_name), "r", encoding="utf-8") as f:
                bot_token = f.read().strip()
        proxy_url = cfg.proxy_url if cfg.proxy_url else None
        self.bot = Bot(token=bot_token, proxy=proxy_url)
        self.dp = Dispatcher(self.bot)
        self.dp.register_message_handler(self.thread_welcome_message, commands=["start"])
        self.dp.register_message_handler(self.thread_get_message)
        self.dp.register_message_handler(self.thread_get_json_document, content_types=types.ContentType.DOCUMENT)
        self.dp.register_callback_query_handler(self.thread_push_button)
        await self.dp.start_polling()

        # Thread(target=self.no_sleep_callback).start()

    # =============================================================================
    # Additional telegram actions

    @staticmethod
    def get_user_profile_name(message) -> str:
        message = message or message.message
        user_name = cfg.user_name_template.replace("FIRSTNAME", message.from_user.first_name or "")
        user_name = user_name.replace("LASTNAME", message.from_user.last_name or "")
        user_name = user_name.replace("USERNAME", message.from_user.username or "")
        user_name = user_name.replace("ID", str(message.from_user.id) or "")
        return user_name

    async def make_template_message(self, request: str, chat_id: int, custom_string="") -> str:
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
                    await utils.prepare_text(user.greeting, user, "to_user"),
                )
                msg = msg.replace(
                    "_CUSTOM_STRING_",
                    await utils.prepare_text(custom_string, user, "to_user"),
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

    async def thread_get_json_document(self, message: Message):
        chat_id = message.chat.id
        if not utils.check_user_permission(chat_id):
            return False
        utils.init_check_user(self.users, chat_id)
        user = self.users[chat_id]
        default_user_file_path = str(Path(f"{cfg.history_dir_path}/{str(chat_id)}.json"))

        file = await self.bot.get_file(file_id=message.document.file_id)
        file_path = file.file_path
        await self.bot.download_file(file_path=file_path, destination=default_user_file_path)

        user.load_user_history(default_user_file_path)
        if len(user.history) > 0:
            last_message = user.history_last_out
        else:
            last_message = "<no message in history>"
        send_text = await self.make_template_message("hist_loaded", chat_id, last_message)
        await self.bot.send_message(
            chat_id=chat_id,
            text=send_text,
            reply_markup=self.get_initial_keyboard(chat_id, user),
            parse_mode="HTML",
        )

    async def start_send_typing_status(self, chat_id: int) -> Event:
        typing_active = Event()
        typing_active.set()
        asyncio.create_task(self.thread_typing_status(chat_id, typing_active))
        return typing_active

    async def thread_typing_status(self, chat_id: int, typing_active: Event):
        limit_counter = int(cfg.generation_timeout / 5)
        while typing_active.is_set() and limit_counter > 0:
            await self.bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(5)
            limit_counter -= 1

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError),
        max_time=10,
    )
    async def send_sd_image(self, message, answer: str, user_text: str):
        chat_id = message.chat.id
        try:
            file_list = await self.SdApi.get_image(answer)
            answer = answer.replace(cfg.sd_api_prompt_of.replace("OBJECT", user_text[1:].strip()), "")
            for char in ["[", "]", "{", "}", "(", ")", "*", '"', "'"]:
                answer = answer.replace(char, "")
            if len(answer) > 1023:
                answer = answer[:1023]
            if len(file_list) > 0:
                for image_path in file_list:
                    if exists(image_path):
                        await self.bot.send_photo(caption=answer, chat_id=chat_id, photo=InputFile(image_path))
                        remove(image_path)
        except Exception as e:
            logging.error("send_sd_image: " + str(e))
            await self.bot.send_message(text=answer, chat_id=chat_id)

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError),
        max_time=10,
    )
    async def clean_last_message_markup(self, chat_id: int):
        if chat_id in self.users and len(self.users[chat_id].msg_id) > 0:
            last_msg = self.users[chat_id].msg_id[-1]
            try:
                await self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=last_msg, reply_markup=None)
            except Exception as exception:
                logging.info("clean_last_message_markup: " + str(exception))

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError),
        max_time=10,
    )
    async def send_message(self, chat_id: int, text: str) -> Message:
        user = self.users[chat_id]
        text = await utils.prepare_text(text, user, "to_user")
        if user.silero_speaker == "None" or user.silero_model_id == "None":
            message = await self.bot.send_message(
                text=text,
                chat_id=chat_id,
                parse_mode="HTML",
                reply_markup=self.get_chat_keyboard(chat_id, True),
            )
        else:
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = await self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                message = await self.bot.send_audio(
                    chat_id=chat_id,
                    audio=InputFile(audio_path),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=self.get_chat_keyboard(chat_id, True),
                )
            else:
                message = await self.bot.send_message(
                    text=text,
                    chat_id=chat_id,
                    parse_mode="HTML",
                    reply_markup=self.get_chat_keyboard(chat_id, True),
                )
        return message

    @backoff.on_exception(
        backoff.expo,
        (urllib3.exceptions.HTTPError, urllib3.exceptions.ConnectTimeoutError),
        max_time=10,
    )
    async def edit_message(
        self,
        cbq,
        chat_id: int,
        text: str,
        message_id: int,
    ):
        user = self.users[chat_id]
        text = await utils.prepare_text(text, user, "to_user")
        if cbq.message.text is not None:
            await self.bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                parse_mode="HTML",
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(chat_id),
            )
        if cbq.message.audio is not None and user.silero_speaker != "None" and user.silero_model_id != "None":
            if ":" in text:
                audio_text = ":".join(text.split(":")[1:])
            else:
                audio_text = text
            audio_path = await self.silero.get_audio(text=audio_text, user_id=chat_id, user=user)
            if audio_path is not None:
                await self.bot.edit_message_media(
                    chat_id=chat_id,
                    media=InputMediaAudio(media=normpath(audio_path)),
                    message_id=message_id,
                    reply_markup=self.get_chat_keyboard(chat_id),
                )
        if cbq.message.caption is not None:
            await self.bot.edit_message_caption(
                chat_id=chat_id,
                caption=text,
                parse_mode="HTML",
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(chat_id),
            )

    # =============================================================================
    # Message handler

    async def thread_welcome_message(self, message: types.Message):
        chat_id = message.chat.id
        if not utils.check_user_permission(chat_id):
            return False
        utils.init_check_user(self.users, chat_id)
        send_text = await self.make_template_message("char_loaded", chat_id)
        await self.bot.send_message(
            chat_id=chat_id,
            text=send_text,
            reply_to_message_id=None,
            reply_markup=self.get_initial_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
            parse_mode="HTML",
        )

    async def thread_get_message(self, message: types.Message):
        # Extract user input and chat ID
        user_text = message.text
        chat_id = message.chat.id
        utils.init_check_user(self.users, chat_id)
        user = self.users[chat_id]
        # check permission and flooding
        if not utils.check_user_permission(chat_id):
            return False
        if not user.check_flooding(cfg.flood_avoid_delay):
            return False
        if cfg.only_mention_in_chat and message.chat.type != "CHAT_PRIVATE":
            if "".join(["@", message.from_user.username]) in user_text:
                user_text = user_text.replace("".join(["@", message.from_user.username]), "")
            else:
                return
        # Send "typing" message
        typing = await self.start_send_typing_status(chat_id)
        try:
            if utils.check_user_rule(chat_id=chat_id, option=const.GET_MESSAGE) is not True:
                return False
            if not user_text.startswith(tuple(cfg.sd_api_prefixes)):
                user_text = await utils.prepare_text(user_text, user, "to_model")
            answer, system_message = await tp.aget_answer(
                text_in=user_text,
                user=user,
                bot_mode=cfg.bot_mode,
                generation_params=cfg.generation_params,
                name_in=self.get_user_profile_name(message),
            )
            if system_message == const.MSG_SYSTEM:
                await message.reply(text=answer)
            elif system_message == const.MSG_SD_API:
                user.truncate_last_message()
                await self.send_sd_image(message, answer, user_text)
            else:
                if system_message == const.MSG_DEL_LAST:
                    await message.delete()
                # message = self.send_message(text=answer, chat_id=chat_id, context=context)
                reply = await self.send_message(text=answer, chat_id=chat_id)
                # Clear buttons on last message (if they exist in current thread)
                await self.clean_last_message_markup(chat_id)
                # Add message ID to message history
                user.msg_id.append(reply.message_id)
                # Save user history
                user.save_user_history(chat_id, cfg.history_dir_path)
        except Exception as e:
            logging.error("thread_get_message" + str(e) + str(e.args))
        finally:
            pass
            typing.clear()

    # =============================================================================
    # button
    async def thread_push_button(self, cbq: types.CallbackQuery):
        chat_id = cbq.message.chat.id
        msg_id = cbq.message.message_id
        option = cbq.data
        if not utils.check_user_permission(chat_id):
            return False
        # Send "typing" message
        typing = await self.start_send_typing_status(chat_id)
        await self.bot.answer_callback_query(cbq.id)
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
                    await cbq.message.edit_reply_markup(reply_markup=None)
                    return
                else:
                    # if msg list not empty but  lost button - clear markup and return
                    if msg_id != self.users[chat_id].msg_id[-1]:
                        await cbq.message.edit_reply_markup(reply_markup=None)
                        return
            await self.handle_button_option(option, chat_id, cbq)
            self.users[chat_id].save_user_history(chat_id, cfg.history_dir_path)
        except Exception as e:
            logging.error("thread_push_button " + str(e) + str(e.args))
        finally:
            pass
            typing.clear()

    async def handle_button_option(self, option, chat_id, cbq: types.CallbackQuery):
        if option == const.BTN_RESET and utils.check_user_rule(chat_id, option):
            await self.on_reset_history_button(cbq)
        elif option == const.BTN_CONTINUE and utils.check_user_rule(chat_id, option):
            await self.on_continue_message_button(cbq)
        elif option == const.BTN_IMPERSONATE and utils.check_user_rule(chat_id, option):
            await self.on_impersonate_button(cbq)
        elif option == const.BTN_NEXT and utils.check_user_rule(chat_id, option):
            await self.on_next_message_button(cbq)
        elif option == const.BTN_IMPERSONATE_INIT and utils.check_user_rule(chat_id, option):
            await self.on_impersonate_button(cbq, initial=True)
        elif option == const.BTN_NEXT_INIT and utils.check_user_rule(chat_id, option):
            await self.on_next_message_button(cbq, initial=True)
        elif option == const.BTN_DEL_WORD and utils.check_user_rule(chat_id, option):
            await self.on_delete_word_button(cbq)
        elif option == const.BTN_PREVIOUS and utils.check_user_rule(chat_id, option):
            await self.on_previous_message_button(cbq)
        elif option == const.BTN_REGEN and utils.check_user_rule(chat_id, option):
            await self.on_regenerate_message_button(cbq)
        elif option == const.BTN_CUTOFF and utils.check_user_rule(chat_id, option):
            await self.on_cutoff_message_button(cbq)
        elif option == const.BTN_DOWNLOAD and utils.check_user_rule(chat_id, option):
            await self.on_download_json_button(cbq)
        elif option == const.BTN_OPTION and utils.check_user_rule(chat_id, option):
            await self.show_options_button(cbq)
        elif option == const.BTN_DELETE and utils.check_user_rule(chat_id, option):
            await self.on_delete_pressed_button(cbq)
        elif option.startswith(const.BTN_CHAR_LIST) and utils.check_user_rule(chat_id, option):
            await self.keyboard_characters_button(cbq, option=option)
        elif option.startswith(const.BTN_CHAR_LOAD) and utils.check_user_rule(chat_id, option):
            await self.load_character_button(cbq, option=option)
        elif option.startswith(const.BTN_PRESET_LIST) and utils.check_user_rule(chat_id, option):
            await self.keyboard_presets_button(cbq, option=option)
        elif option.startswith(const.BTN_PRESET_LOAD) and utils.check_user_rule(chat_id, option):
            await self.load_presets_button(cbq, option=option)
        elif option.startswith(const.BTN_MODEL_LIST) and utils.check_user_rule(chat_id, option):
            await self.on_keyboard_models_button(cbq, option=option)
        elif option.startswith(const.BTN_MODEL_LOAD) and utils.check_user_rule(chat_id, option):
            await self.on_load_model_button(cbq, option=option)
        elif option.startswith(const.BTN_LANG_LIST) and utils.check_user_rule(chat_id, option):
            await self.on_keyboard_language_button(cbq, option=option)
        elif option.startswith(const.BTN_LANG_LOAD) and utils.check_user_rule(chat_id, option):
            await self.on_load_language_button(cbq, option=option)
        elif option.startswith(const.BTN_VOICE_LIST) and utils.check_user_rule(chat_id, option):
            await self.on_keyboard_voice_button(cbq, option=option)
        elif option.startswith(const.BTN_VOICE_LOAD) and utils.check_user_rule(chat_id, option):
            await self.on_load_voice_button(cbq, option=option)

    async def show_options_button(self, cbq: CallbackQuery):
        chat_id = cbq.message.chat.id
        user = self.users[chat_id]
        send_text = utils.get_conversation_info(user)
        await self.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            reply_markup=self.get_options_keyboard(chat_id, user),
            parse_mode="HTML",
        )

    async def on_delete_pressed_button(self, cbq):
        chat_id = cbq.message.chat.id
        message_id = cbq.message.message_id
        await self.bot.delete_message(chat_id=chat_id, message_id=message_id)

    async def on_impersonate_button(self, cbq, initial=False):
        chat_id = cbq.message.chat.id
        message_id = cbq.message.message_id
        user = self.users[chat_id]
        if initial:
            await self.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.get_options_keyboard(chat_id, user),
            )
        else:
            await self.clean_last_message_markup(chat_id)
        answer, _ = await tp.aget_answer(
            text_in=const.GENERATOR_MODE_IMPERSONATE,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(cbq),
        )
        message = await self.send_message(text=answer, chat_id=chat_id)
        user.msg_id.append(message.message_id)
        user.save_user_history(chat_id, cfg.history_dir_path)

    async def on_next_message_button(self, cbq, initial=False):
        chat_id = cbq.message.chat.id
        message_id = cbq.message.message_id
        user = self.users[chat_id]
        if initial:
            await self.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.get_options_keyboard(chat_id, user),
            )
        else:
            await self.clean_last_message_markup(chat_id)
        answer, _ = await tp.aget_answer(
            text_in=const.GENERATOR_MODE_NEXT,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(cbq),
        )
        message = await self.send_message(text=answer, chat_id=chat_id)
        user.msg_id.append(message.message_id)
        user.save_user_history(chat_id, cfg.history_dir_path)

    async def on_continue_message_button(self, cbq):
        chat_id = cbq.message.chat.id
        message = cbq.message
        user = self.users[chat_id]
        # get answer and replace message text!
        answer, _ = await tp.aget_answer(
            text_in=const.GENERATOR_MODE_CONTINUE,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(cbq),
        )
        await self.edit_message(
            text=answer,
            chat_id=chat_id,
            message_id=message.message_id,
        )
        user.save_user_history(chat_id, cfg.history_dir_path)

    async def on_previous_message_button(self, cbq):
        chat_id = cbq.message.chat.id
        message = cbq.message
        user = self.users[chat_id]
        # get answer and replace message text!
        answer = user.back_to_previous_out(msg_id=message.message_id)
        if answer is not None:
            await self.edit_message(text=answer, chat_id=chat_id, message_id=message.message_id, cbq=cbq)
        user.save_user_history(chat_id, cfg.history_dir_path)

    async def on_delete_word_button(self, cbq):
        chat_id = cbq.message.chat.id
        user = self.users[chat_id]
        answer, return_msg_action = await tp.aget_answer(
            text_in=const.GENERATOR_MODE_DEL_WORD,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(cbq),
        )
        if return_msg_action != const.MSG_NOTHING_TO_DO:
            await self.edit_message(text=answer, chat_id=chat_id, message_id=user.msg_id[-1], cbq=cbq)
            user.save_user_history(chat_id, cfg.history_dir_path)

    async def on_regenerate_message_button(self, cbq):
        chat_id = cbq.message.chat.id
        msg = cbq.message
        user = self.users[chat_id]
        await self.clean_last_message_markup(chat_id)
        # get answer and replace message text!
        answer, _ = await tp.aget_answer(
            text_in=const.GENERATOR_MODE_REGENERATE,
            user=user,
            bot_mode=cfg.bot_mode,
            generation_params=cfg.generation_params,
            name_in=self.get_user_profile_name(cbq),
        )
        await self.edit_message(
            text=answer,
            chat_id=chat_id,
            message_id=msg.message_id,
            cbq=cbq,
        )
        user.save_user_history(chat_id, cfg.history_dir_path)

    async def on_cutoff_message_button(self, cbq):
        chat_id = cbq.message.chat.id
        user = self.users[chat_id]
        # Edit or delete last message ID (strict lines)
        last_msg_id = user.msg_id[-1]
        await self.bot.delete_message(chat_id=chat_id, message_id=last_msg_id)
        # Remove last message and bot answer from history
        user.truncate_last_message()
        # If there is previous message - add buttons to previous message
        if user.msg_id:
            message_id = user.msg_id[-1]
            await self.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=self.get_chat_keyboard(chat_id),
            )
        user.save_user_history(chat_id, cfg.history_dir_path)

    async def on_download_json_button(self, cbq):
        chat_id = cbq.message.chat.id
        user = self.users[chat_id]
        if chat_id not in self.users:
            return

        user_file = io.StringIO(self.users[chat_id].to_json())
        send_caption = await self.make_template_message("hist_to_chat", chat_id)
        await self.bot.send_document(
            chat_id=chat_id,
            caption=send_caption,
            document=InputFile(user_file, filename=user.name2 + ".json"),
        )

    async def on_reset_history_button(self, cbq):
        # check if it is a callback_query or a command
        if cbq:
            chat_id = cbq.message.chat.id
        else:
            chat_id = cbq.chat.id
        if chat_id not in self.users:
            return
        user = self.users[chat_id]
        if user.msg_id:
            await self.clean_last_message_markup(chat_id)
        user.reset()
        user.load_character_file(cfg.characters_dir_path, user.char_file)
        send_text = await self.make_template_message("mem_reset", chat_id)
        await self.bot.send_message(
            chat_id=chat_id,
            text=send_text,
            reply_markup=self.get_initial_keyboard(chat_id, user),
            parse_mode="HTML",
        )

    # =============================================================================
    # switching keyboard
    async def on_load_model_button(self, cbq, option: str):
        if tp.generator.get_model_list is not None:
            model_list = tp.generator.get_model_list()
            model_file = model_list[int(option.replace(const.BTN_MODEL_LOAD, ""))]
            chat_id = cbq.effective_chat.id
            send_text = "Loading " + model_file + ". 🪄"
            message_id = cbq.message.message_id
            await self.bot.edit_message_text(
                text=send_text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
            )
            try:
                tp.generator.load_model(model_file)
                send_text = await self.make_template_message(
                    request="model_loaded", chat_id=chat_id, custom_string=model_file
                )
                await self.bot.edit_message_text(
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
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Error during " + model_file + " loading. ⛔",
                    parse_mode="HTML",
                    reply_markup=self.get_options_keyboard(
                        chat_id, self.users[chat_id] if chat_id in self.users else None
                    ),
                )
                raise e

    async def on_keyboard_models_button(self, cbq, option: str):
        if tp.generator.get_model_list() is not None:
            chat_id = cbq.message.chat.id
            msg = cbq.message
            model_list = tp.generator.get_model_list()
            if option == const.BTN_MODEL_LIST + const.BTN_OPTION:
                await self.bot.edit_message_reply_markup(
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
            await self.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=msg.message_id,
                reply_markup=characters_buttons,
            )

    async def load_presets_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        preset_char_num = int(option.replace(const.BTN_PRESET_LOAD, ""))
        cfg.preset_file = utils.parse_presets_dir()[preset_char_num]
        cfg.load_preset(preset_file=cfg.preset_file)
        user = self.users[chat_id]
        send_text = utils.get_conversation_info(user)
        message_id = cbq.message.message_id
        await self.bot.edit_message_text(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id, user),
        )

    async def keyboard_presets_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        msg = cbq.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_PRESET_LIST + const.BTN_OPTION:
            await self.bot.edit_message_reply_markup(
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
        await self.bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=msg.message_id, reply_markup=characters_buttons
        )

    async def load_character_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        char_num = int(option.replace(const.BTN_CHAR_LOAD, ""))
        char_list = utils.parse_characters_dir()
        await self.clean_last_message_markup(chat_id)
        utils.init_check_user(self.users, chat_id)
        user = self.users[chat_id]
        char_file = char_list[char_num]
        user.load_character_file(characters_dir_path=cfg.characters_dir_path, char_file=char_file)
        #  If there was conversation with this character_file - load history
        user.find_and_load_user_char_history(chat_id, cfg.history_dir_path)
        if len(user.history) > 0:
            send_text = await self.make_template_message("hist_loaded", chat_id, user.history_last_out)
        else:
            send_text = await self.make_template_message("char_loaded", chat_id)
        await self.bot.send_message(
            text=send_text,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_initial_keyboard(chat_id, self.users[chat_id] if chat_id in self.users else None),
        )

    async def keyboard_characters_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        msg = cbq.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_CHAR_LIST + const.BTN_OPTION:
            await self.bot.edit_message_reply_markup(
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
        await self.bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=msg.message_id, reply_markup=characters_buttons
        )

    async def on_load_language_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        message_id = cbq.message.message_id
        user = self.users[chat_id]
        lang_num = int(option.replace(const.BTN_LANG_LOAD, ""))
        language = list(cfg.language_dict.keys())[lang_num]
        self.users[chat_id].language = language
        send_text = utils.get_conversation_info(user)
        await self.bot.edit_message_text(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id, user),
        )

    async def on_keyboard_language_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        msg = cbq.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_LANG_LIST + const.BTN_OPTION:
            await self.bot.edit_message_reply_markup(
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
        await self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg.message_id, reply_markup=lang_buttons)

    async def on_load_voice_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        user = self.users[chat_id]
        male = Silero.voices[user.language]["male"]
        female = Silero.voices[user.language]["female"]
        voice_dict = ["None"] + male + female
        voice_num = int(option.replace(const.BTN_VOICE_LOAD, ""))
        user.silero_speaker = voice_dict[voice_num]
        user.silero_model_id = Silero.voices[user.language]["model"]
        send_text = utils.get_conversation_info(user)
        message_id = cbq.message.message_id
        await self.bot.edit_message_text(
            text=send_text,
            message_id=message_id,
            chat_id=chat_id,
            parse_mode="HTML",
            reply_markup=self.get_options_keyboard(chat_id, user),
        )

    async def on_keyboard_voice_button(self, cbq, option: str):
        chat_id = cbq.message.chat.id
        msg = cbq.message
        #  if "return character_file markup" button - clear markup
        if option == const.BTN_VOICE_LIST + const.BTN_OPTION:
            await self.bot.edit_message_reply_markup(
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
        await self.bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg.message_id, reply_markup=voice_buttons)

    # =============================================================================
    # load characters char_file from ./characters
    def get_initial_keyboard(self, chat_id, user: User):
        options = buttons.get_options_keyboard(chat_id=chat_id, user=user)
        chat_actions = buttons.get_chat_init_keyboard(chat_id=chat_id)
        return self.keyboard_raw_to_keyboard_tg([options[0], chat_actions[0]])

    def get_options_keyboard(self, chat_id, user: User):
        return self.keyboard_raw_to_keyboard_tg(buttons.get_options_keyboard(chat_id=chat_id, user=user))

    def get_chat_keyboard(self, chat_id=0, no_previous=False):
        if chat_id in self.users:
            user = self.users[chat_id]
        else:
            user = None
        return self.keyboard_raw_to_keyboard_tg(buttons.get_chat_keyboard(chat_id, user, no_previous))

    def get_switch_keyboard(
        self,
        opt_list: list,
        shift: int,
        data_list: str,
        data_load: str,
        keyboard_rows=6,
        keyboard_column=2,
    ):
        return self.keyboard_raw_to_keyboard_tg(
            buttons.get_switch_keyboard(
                opt_list=opt_list,
                shift=shift,
                data_list=data_list,
                data_load=data_load,
                keyboard_rows=keyboard_rows,
                keyboard_column=keyboard_column,
            )
        )

    @staticmethod
    def keyboard_raw_to_keyboard_tg(keyboard_raw):
        keyboard_tg = []
        for buttons_row in keyboard_raw:
            keyboard_tg.append([])
            for button_dict in buttons_row:
                keyboard_tg[-1].append(InlineKeyboardButton(**button_dict))
        return InlineKeyboardMarkup(inline_keyboard=keyboard_tg)
