import time

import server
from modules import shared
from modules.text_generation import encode
from modules.text_generation import generate_reply
from modules.utils import get_available_models

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator


class Generator(AbstractGenerator):
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = True  # if preset_file changing allowed.

    def __init__(self, model_path="", n_ctx=2048, n_gpu_layers=0):
        pass

    @staticmethod
    def generate_answer(
        prompt, generation_params, eos_token, stopping_strings, default_answer, turn_template="", **kwargs
    ):
        generation_params.update({"turn_template": turn_template})
        generation_params.update(
            {
                "stream": False,
                "max_new_tokens": int(
                    generation_params.get("max_new_tokens", generation_params.get("max_length", 200))
                ),
                "do_sample": bool(generation_params.get("do_sample", True)),
                "temperature": float(generation_params.get("temperature", 0.5)),
                "top_p": float(generation_params.get("top_p", 1)),
                "typical_p": float(generation_params.get("typical_p", generation_params.get("typical", 1))),
                "epsilon_cutoff": float(generation_params.get("epsilon_cutoff", 0)),
                "eta_cutoff": float(generation_params.get("eta_cutoff", 0)),
                "tfs": float(generation_params.get("tfs", 1)),
                "top_a": float(generation_params.get("top_a", 0)),
                "repetition_penalty": float(
                    generation_params.get("repetition_penalty", generation_params.get("rep_pen", 1.1))
                ),
                "repetition_penalty_range": int(generation_params.get("repetition_penalty_range", 0)),
                "encoder_repetition_penalty": float(generation_params.get("encoder_repetition_penalty", 1.0)),
                "top_k": int(generation_params.get("top_k", 0)),
                "min_length": int(generation_params.get("min_length", 0)),
                "no_repeat_ngram_size": int(generation_params.get("no_repeat_ngram_size", 0)),
                "num_beams": int(generation_params.get("num_beams", 1)),
                "penalty_alpha": float(generation_params.get("penalty_alpha", 0)),
                "length_penalty": float(generation_params.get("length_penalty", 1)),
                "early_stopping": bool(generation_params.get("early_stopping", False)),
                "mirostat_mode": int(generation_params.get("mirostat_mode", 0)),
                "mirostat_tau": float(generation_params.get("mirostat_tau", 5)),
                "mirostat_eta": float(generation_params.get("mirostat_eta", 0.1)),
                "seed": int(generation_params.get("seed", -1)),
                "add_bos_token": bool(generation_params.get("add_bos_token", True)),
                "truncation_length": int(
                    generation_params.get(
                        "truncation_length",
                        generation_params.get("max_context_length", 2048),
                    )
                ),
                "ban_eos_token": bool(generation_params.get("ban_eos_token", False)),
                "skip_special_tokens": bool(generation_params.get("skip_special_tokens", True)),
                "custom_stopping_strings": "",  # leave this blank
                "stopping_strings": generation_params.get("stopping_strings", []),
            }
        )
        generator = generate_reply(question=prompt, state=generation_params, stopping_strings=stopping_strings)
        # This is "bad" implementation of getting answer, should be reworked
        answer = default_answer
        for a in generator:
            if isinstance(a, str):
                answer = a
            else:
                answer = a[0]
        # make adds
        return answer

    def tokens_count(self, text: str):
        return len(encode(text)[0])

    def get_model_list(self):
        return get_available_models()

    def load_model(self, model_file: str):
        server.unload_model()
        server.model_name = model_file
        if model_file != "":
            shared.model, shared.tokenizer = server.load_model(shared.model_name)
        while server.load_model is None:
            time.sleep(1)
        return True
