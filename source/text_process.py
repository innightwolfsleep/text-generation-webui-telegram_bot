import importlib
import logging
from threading import Lock
from typing import Tuple, Dict
from re import split, sub


try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator

try:
    from extensions.telegram_bot.source.user import User as User
    import extensions.telegram_bot.source.const as const
    from extensions.telegram_bot.source.conf import cfg
except ImportError:
    from source.user import User as User
    import source.const as const
    from source.conf import cfg

# Define generator lock to prevent GPU overloading
generator_lock = Lock()

# Generator obj
generator: AbstractGenerator
debug_flag = True


# ====================================================================================
# TEXT LOGIC
def get_answer(text_in: str, user: User, bot_mode: str, generation_params: Dict, name_in="") -> Tuple[str, str]:
    # if generation will fail, return "fail" answer
    answer = const.GENERATOR_FAIL
    # default result action - message
    return_msg_action = const.MSG_SEND
    # if user is default equal to user1
    name_in = user.name1 if name_in == "" else name_in
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
            user.history[-1]["out"] = text_in[1:]
            return_msg_action = const.MSG_DEL_LAST
            generator_lock.release()
            return user.history[-1]["out"], return_msg_action
        if text_in == const.GENERATOR_MODE_DEL_WORD:
            # If user_in starts with replace_prefix - fully replace last message
            # get and change last message
            last_message = user.history[-1]["out"]
            last_word = split(r"\n|\.+ +|: +|! +|\? +|\' +|\" +|; +|\) +|\* +", last_message)[-1]
            if len(last_word) == 0 and len(last_message) > 1:
                last_word = " "
            new_last_message = last_message[: -(len(last_word))]
            new_last_message = new_last_message.strip()
            if len(new_last_message) == 0:
                return_msg_action = const.MSG_NOTHING_TO_DO
            else:
                user.change_last_message(history_answer=new_last_message)
            generator_lock.release()
            return user.history[-1]["out"], return_msg_action

        # Preprocessing: actions which not depends on user input:
        if bot_mode in [const.MODE_QUERY]:
            user.history = []

        # if regenerate - msg_id the same, text and name the same. But history clearing.:
        if text_in == const.GENERATOR_MODE_REGENERATE:
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
        context_len = get_tokens_count(context)
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

        prompt = ""
        for s in reversed(conversation):
            s = "\n" + cfg.bot_prompt_begin + s + cfg.bot_prompt_end if len(s) > 0 else s
            s_len = get_tokens_count(s)
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
        answer = generate_answer(
            prompt=prompt,
            generation_params=generation_params,
            eos_token=eos_token,
            stopping_strings=stopping_strings,
            default_answer=answer,
            turn_template=user.turn_template,
        )
        # If generation result zero length - return  "Empty answer."
        if cfg.bot_prompt_end != "" and answer.endswith(cfg.bot_prompt_end):
            answer = answer[: -len(cfg.bot_prompt_end)]
        if len(answer) < 1:
            answer = const.GENERATOR_EMPTY_ANSWER
        # Final return
        if answer not in [const.GENERATOR_EMPTY_ANSWER, const.GENERATOR_FAIL]:
            # if everything ok - add generated answer in history and return
            # last
            for end in stopping_strings:
                if answer.endswith(end):
                    answer = answer[: -len(end)]
            user.history[-1]["out"] = user.history[-1]["out"] + " " + answer
        generator_lock.release()
        return user.history[-1]["out"], return_msg_action
    except Exception as exception:
        logging.error("get_answer (generator part) " + str(exception) + str(exception.args))
        # anyway, release generator lock. Then return
        generator_lock.release()
        return_msg_action = const.MSG_SYSTEM
        return user.history[-1]["out"], return_msg_action


# ====================================================================================
# GENERATOR
# import generator
def init(script="generator_llama_cpp.py", model_path="", n_ctx=4096, n_gpu_layers=0):
    """Initiate generator type
    generator - is a class Generator from package generators/script
    Generator class should contain method:
       __init__() - method to initiate model
       get_answer() - method get answer
       tokens_count(str) - method to get str length in tokens
    If Generator.model_change_allowed = True - also method:
       get_model_list() - get list of available models
       load_model(str) - load new model

    Args:
      script: script type, one of generators/*.py files
      model_path: path to model file, if generator needs
      n_ctx: context length, if generator needs
      n_gpu_layers: n_gpu_layers for llama
    """
    logging.info(f"### text_process INIT generator: {script}, model: {model_path} ###")
    try:
        generator_class = getattr(importlib.import_module("source.generators." + script), "Generator")
    except ImportError:
        generator_class = getattr(
            importlib.import_module("extensions.telegram_bot.source.generators." + script), "Generator"
        )
    global generator
    generator = generator_class(model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
    logging.info(f"### text_process INIT generator: {script}, model: {model_path} DONE ###")


def generate_answer(
    prompt, generation_params, eos_token, stopping_strings, default_answer: str, turn_template=""
) -> str:
    """Generate and return answer string.

    Args:
      prompt: user prompt
      generation_params: dict with various generator params
      eos_token: list with end of string tokens
      stopping_strings: list with strings stopping generating
      default_answer: if generating fails, default_answer will be returned
      turn_template: turn template if generator needs it

    Returns:
      generation result string
    """
    # Preparing, add stopping_strings
    answer = default_answer
    generation_params.update({"turn_template": turn_template})
    if debug_flag:
        print("stopping_strings =", stopping_strings)
        print(prompt)
    try:
        answer = generator.generate_answer(
            prompt,
            generation_params,
            eos_token,
            stopping_strings,
            default_answer,
            turn_template,
        )
    except Exception as exception:
        print("generation error:", str(exception) + str(exception.args))
    if debug_flag:
        print(answer)
    return answer


def get_tokens_count(text: str):
    """Return string length in tokens

    Args:
      text: text to be counted

    Returns:
      text token length (int)
    """
    return generator.tokens_count(text)


def get_model_list():
    """Return list of available models

    Returns:
      list of available models
    """
    return generator.get_model_list()


def load_model(model_file: str):
    """Change current llm model to model_file

    Args:
      model_file: model file to be loaded

    Returns:
      True if loading successful, otherwise False
    """
    return generator.load_model(model_file)
