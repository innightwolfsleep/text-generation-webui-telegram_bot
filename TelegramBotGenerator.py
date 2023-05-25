import time
import server
from modules.text_generation import generate_reply
from modules.text_generation import encode
from modules import shared


def get_answer(
        prompt,
        generation_params,
        eos_token,
        stopping_strings,
        default_answer,
        user,
        turn_template='',
        **kwargs):
    generation_params.update({"turn_template": turn_template})
    generation_params.update({"name1": user['name1']})
    generation_params.update({"name2": user['name2']})
    generation_params.update({"context": user['context']})
    generation_params.update({"greeting": user['greeting']})
    generation_params.update({"epsilon_cutoff": 0,
                              "eta_cutoff": 0,
                              'mirostat_mode': 0,
                              'mirostat_tau': 5,
                              'mirostat_eta': 0.1,
                              "stream": False,
                             })
    stopping_strings.append(r"\end{code}")
    generator = generate_reply(question=prompt,
                               state=generation_params,
                               eos_token=eos_token,
                               stopping_strings=stopping_strings)
    # This is "bad" implementation of getting answer, should be reworked
    answer = default_answer
    for a in generator:
        if isinstance(a, str):
            answer = a
        else:
            answer = a[0]
    return answer


def tokens_count(text: str):
    return len(encode(text)[0])


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
