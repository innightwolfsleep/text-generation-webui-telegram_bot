import logging
from re import split, sub
from threading import Lock
from time import sleep
from typing import Tuple, Dict

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator

try:
    import extensions.telegram_bot.source.const as const
    import extensions.telegram_bot.source.utils as utils
    import extensions.telegram_bot.source.generator as generator
    from extensions.telegram_bot.source.user import User as User
    from extensions.telegram_bot.source.conf import cfg
    from extensions.telegram_bot.source.conf import cfg
except ImportError:
    import source.const as const
    import source.utils as utils
    import source.generator as generator
    from source.user import User as User
    from source.conf import cfg

# Define generator lock to prevent GPU overloading
generator_lock = Lock()

# Generator obj
debug_flag = True


# ====================================================================================
# TEXT LOGIC
async def aget_answer(text_in: str, user: User, bot_mode: str, generation_params: Dict, name_in="") -> Tuple[str, str]:
    return await get_answer(text_in, user, bot_mode, generation_params, name_in)


@utils.async_wrap
def get_answer(text_in: str, user: User, bot_mode: str, generation_params: Dict, name_in=""):
    # additional delay option
    if cfg.answer_delay > 0:
        sleep(cfg.answer_delay)
    # if generation will fail, return "fail" answer
    answer = const.GENERATOR_FAIL
    # default result action - message
    return_msg_action = const.MSG_SEND
    # if user is default equal to user1
    name_in = user.name1 if name_in == "" else name_in
    # for regeneration result checking
    previous_result = ""
    # acquire generator lock if we can
    generator_lock.acquire(timeout=cfg.generation_timeout)
    # user_input preprocessing
    try:
        # Preprocessing: actions which return result immediately:
        if text_in.startswith(tuple(cfg.permanent_change_name2_prefixes)):
            # If user_in starts with perm_prefix - just replace name2
            user.name2 = text_in[2:]
            return_msg_action = const.MSG_SYSTEM
            generator_lock.release()
            return "New bot name: " + user.name2, return_msg_action
        if text_in.startswith(tuple(cfg.permanent_change_name1_prefixes)):
            # If user_in starts with perm_prefix - just replace name2
            user.name1 = text_in[2:]
            return_msg_action = const.MSG_SYSTEM
            generator_lock.release()
            return "New user name: " + user.name1, return_msg_action
        if text_in.startswith(tuple(cfg.permanent_add_context_prefixes)):
            # If user_in starts with perm_prefix - just replace name2
            user.context += "\n" + text_in[2:]
            return_msg_action = const.MSG_SYSTEM
            generator_lock.release()
            return "Added to context: " + text_in[2:], return_msg_action
        if text_in.startswith(tuple(cfg.replace_prefixes)):
            # If user_in starts with replace_prefix - fully replace last message
            user.change_last_message(history_out=text_in[1:])
            return_msg_action = const.MSG_DEL_LAST
            generator_lock.release()
            return user.history_last_out, return_msg_action
        if text_in == const.GENERATOR_MODE_DEL_WORD:
            # If user_in starts with replace_prefix - fully replace last message
            # get and change last message
            last_message = user.history_last_out
            last_word = split(r"\n|\.+ +|: +|! +|\? +|\' +|\" +|; +|\) +|\* +", last_message)[-1]
            if len(last_word) == 0 and len(last_message) > 1:
                last_word = " "
            new_last_message = last_message[: -(len(last_word))]
            new_last_message = new_last_message.strip()
            if len(new_last_message) == 0:
                return_msg_action = const.MSG_NOTHING_TO_DO
            else:
                user.change_last_message(history_out=new_last_message)
            generator_lock.release()
            return user.history_last_out, return_msg_action

        # Preprocessing: actions which not depends on user input:
        if bot_mode in [const.MODE_QUERY]:
            user.history = []

        # if regenerate - msg_id the same, text and name the same. But history clearing:
        if text_in == const.GENERATOR_MODE_REGENERATE:
            if str(user.msg_id[-1]) not in user.previous_history:
                user.previous_history.update({str(user.msg_id[-1]): []})
            user.previous_history[str(user.msg_id[-1])].append(user.history_last_out)
            text_in = user.text_in[-1]
            name_in = user.name_in[-1]
            last_msg_id = user.msg_id[-1]
            user.truncate_last_message()
            user.msg_id.append(last_msg_id)

        # Preprocessing: add user_in/names/whitespaces to history in right order depends on mode:
        if bot_mode in [const.MODE_NOTEBOOK]:
            # If notebook mode - append to history only user_in, no additional preparing;
            user.text_in.append(text_in)
            user.history_append("", text_in)
        elif text_in == const.GENERATOR_MODE_IMPERSONATE:
            # if impersonate - append to history only "name1:", no adding "" history
            # line to prevent bug in history sequence, add "name1:" prefix for generation
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            user.history_append("", name_in + ":")
        elif text_in == const.GENERATOR_MODE_NEXT:
            # if user_in is "" - no user text, it is like continue generation adding "" history line
            #  to prevent bug in history sequence, add "name2:" prefix for generation
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            user.history_append("", user.name2 + ":")
        elif text_in == const.GENERATOR_MODE_CONTINUE:
            # if user_in is "" - no user text, it is like continue generation
            # adding "" history line to prevent bug in history sequence, add "name2:" prefix for generation
            pass
        elif text_in.startswith(tuple(cfg.sd_api_prefixes)):
            # If user_in starts with prefix - impersonate-like (if you try to get "impersonate view")
            # adding "" line to prevent bug in history sequence, user_in is prefix for bot answer
            user.msg_id.append(0)
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            if len(text_in) == 1:
                user.history_append("", cfg.sd_api_prompt_self)
            else:
                user.history_append("", cfg.sd_api_prompt_of.replace("OBJECT", text_in[1:].strip()))
            return_msg_action = const.MSG_SD_API
        elif text_in.startswith(tuple(cfg.impersonate_prefixes)):
            # If user_in starts with prefix - impersonate-like (if you try to get "impersonate view")
            # adding "" line to prevent bug in history sequence, user_in is prefix for bot answer

            user.text_in.append(text_in)
            user.name_in.append(text_in[1:])
            user.history_append("", text_in[1:] + ":")

        else:
            # If not notebook/impersonate/continue mode then ordinary chat preparing
            # add "name1&2:" to user and bot message (generation from name2 point of view);
            user.text_in.append(text_in)
            user.name_in.append(name_in)
            user.history_append(name_in + ": " + text_in, user.name2 + ":")
    except Exception as exception:
        generator_lock.release()
        logging.error("get_answer (prepare text part) " + str(exception) + str(exception.args))

    # Text processing with LLM
    try:
        # Set eos_token and stopping_strings.
        stopping_strings = generation_params["stopping_strings"].copy()
        eos_token = generation_params["eos_token"]
        if bot_mode in [const.MODE_CHAT, const.MODE_CHAT_R, const.MODE_ADMIN]:
            stopping_strings += [
                name_in + ":",
                user.name1 + ":",
                user.name2 + ":",
            ]
        if cfg.bot_prompt_end != "":
            stopping_strings.append(cfg.bot_prompt_end)

        # adjust context/greeting/example
        if user.context.strip().endswith("\n"):
            context = f"{user.context.strip()}"
        else:
            context = f"{user.context.strip()}\n"
        context = cfg.context_prompt_begin + context + cfg.context_prompt_end
        if len(user.example) > 0:
            example = user.example
        else:
            example = ""
        if len(user.greeting) > 0:
            greeting = "\n" + user.name2 + ": " + user.greeting
        else:
            greeting = ""
        # Make prompt: context + example + conversation history
        available_len = generation_params["truncation_length"]
        context_len = generator.get_tokens_count(context)
        available_len -= context_len
        if available_len < 0:
            available_len = 0
            logging.info("telegram_bot - CONTEXT IS TOO LONG!!!")

        conversation = [example, greeting]
        for i in user.history:
            if len(i["in"]) > 0:
                conversation.append("".join([cfg.user_prompt_begin, i["in"], cfg.user_prompt_end]))
            if len(i["out"]) > 0:
                conversation.append("".join([cfg.bot_prompt_begin, i["out"], cfg.bot_prompt_end]))
        if len(cfg.bot_prompt_end):
            conversation[-1] = conversation[-1][: -len(cfg.bot_prompt_end)]

        prompt = ""
        for s in reversed(conversation):
            s = "\n" + s if len(s) > 0 else s
            s_len = generator.get_tokens_count(s)
            if available_len >= s_len:
                prompt = s + prompt
                available_len -= s_len
            else:
                break
        prompt = context + prompt
        prompt = sub(
            r": +",
            ": ",
            prompt,
        )
        # Generate!
        if debug_flag:
            print(prompt)
        answer = generator.generate_answer(
            prompt=prompt,
            generation_params=generation_params,
            eos_token=eos_token,
            stopping_strings=stopping_strings,
            default_answer=answer,
            turn_template=user.turn_template,
        )
        if debug_flag:
            print(answer)
        # Truncate prompt prefix/postfix
        if len(cfg.bot_prompt_end) > 0 and answer.endswith(cfg.bot_prompt_end):
            answer = answer[: -len(cfg.bot_prompt_end)]
        if len(cfg.bot_prompt_end) > 2 and answer.endswith(cfg.bot_prompt_end[:-1]):
            answer = answer[: -len(cfg.bot_prompt_end[:-1])]
        if len(cfg.bot_prompt_begin) > 0 and answer.startswith(cfg.bot_prompt_begin):
            answer = answer[: -len(cfg.bot_prompt_begin)]
        # If generation result zero length - return  "Empty answer."
        if len(answer) < 1:
            answer = const.GENERATOR_EMPTY_ANSWER
        # Final return
        if answer not in [const.GENERATOR_EMPTY_ANSWER, const.GENERATOR_FAIL]:
            # if everything ok - add generated answer in history and return
            # last
            for end in stopping_strings:
                if answer.endswith(end):
                    answer = answer[: -len(end)]
            user.change_last_message(history_out=user.history_last_out + " " + answer)
        generator_lock.release()
        if len(user.msg_id) > 0:
            if str(user.msg_id[-1]) in user.previous_history:
                if user.previous_history[str(user.msg_id[-1])][-1] == user.history_last_out:
                    return_msg_action = const.MSG_NOTHING_TO_DO
        return user.history_last_out, return_msg_action
    except Exception as exception:
        logging.error("get_answer (generator part) " + str(exception) + str(exception.args))
        # anyway, release generator lock. Then return
        generator_lock.release()
        return_msg_action = const.MSG_SYSTEM
        return user.history_last_out, return_msg_action
