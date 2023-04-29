import server
from modules.text_generation import generate_reply
from modules import shared


def get_answer(prompt, generation_params, eos_token, stopping_strings, default_answer):
    answer = default_answer
    generator = generate_reply(question=prompt,
                               state=generation_params,
                               eos_token=eos_token,
                               stopping_strings=stopping_strings)
    # This is "bad" implementation of getting answer, should be reworked
    for a in generator:
        answer = a
    return answer


def get_server():
    return server


def get_shared():
    return shared
