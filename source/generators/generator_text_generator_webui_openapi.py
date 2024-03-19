import json

import random
import requests

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator


class Generator(AbstractGenerator):
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = False  # if preset_file changing allowed.

    def __init__(
        self,
        model_path="http://127.0.0.1:5000/v1/completions",
        n_ctx=2048,
        seed=0,
        n_gpu_layers=0,
    ):
        self.n_ctx = n_ctx
        self.headers = {"Content-Type": "application/json"}
        if model_path.startswith("http"):
            self.URI = model_path
        else:
            self.URI = "http://127.0.0.1:5000/v1/completions"

    def generate_answer(
        self,
        prompt,
        generation_params,
        eos_token,
        stopping_strings,
        default_answer,
        turn_template="",
        **kwargs,
    ):
        request = {
            "prompt": prompt,
            "max_tokens": generation_params["max_new_tokens"],
            "temperature": generation_params["temperature"],
            "top_p": generation_params["top_p"],
            "seed": random.randint(0, 1000),
        }

        response = requests.post(self.URI, json=request)

        if response.status_code == 200:
            result = response.json()["results"][0]["history"]
            print(json.dumps(result, indent=4))
            return result["visible"][-1][1]
        else:
            return default_answer

    def tokens_count(self, text: str):
        return len(text)

    def get_model_list(self):
        pass

    def load_model(self, model_file: str):
        pass
