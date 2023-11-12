import json

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
        model_path=f"http://localhost:5000/api/v1/chat",
        n_ctx=2048,
        seed=0,
        n_gpu_layers=0,
    ):
        self.n_ctx = n_ctx
        if model_path.startswith("http"):
            self.URI = model_path
        else:
            self.URI = f"http://localhost:5000/api/v1/chat"

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
            "user_input": prompt,
            "eos_token": eos_token,
            "stopping_strings": stopping_strings,
            "turn_template": turn_template,
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
