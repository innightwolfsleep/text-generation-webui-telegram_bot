import time
import server
from modules.text_generation import generate_reply
from modules import shared


def get_answer(
        prompt,
        generation_params,
        eos_token,
        stopping_strings,
        default_answer,
        turn_template='',
        **kwargs):
    generation_params.update({"turn_template": turn_template})
    answer = default_answer
    generator = generate_reply(question=prompt,
                               state=generation_params,
                               eos_token=eos_token,
                               stopping_strings=stopping_strings)
    # This is "bad" implementation of getting answer, should be reworked
    for a in generator:
        answer = a
    return answer


def get_model_list():
    return server.get_available_models()


def load_model(model_file: str):
    server.unload_model()
    server.model_name = model_file
    if model_file != '':
        shared.model, shared.tokenizer = server.load_model(
            shared.model_name)
    while server.load_model is None:
        time.sleep(1)
    return True
