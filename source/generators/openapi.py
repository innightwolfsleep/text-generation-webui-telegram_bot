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
        model_path="None",
        n_ctx=16000,
        seed=0,
        n_gpu_layers=0,
    ):
        self.n_ctx = n_ctx
        self.headers = {"Content-Type": "application/json"}
        if model_path.startswith("None"):
            print("SET OPENAPI URL TO app_config.json - model_path")

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
            "stop": stopping_strings,
            "frequency_penalty": generation_params["frequency_penalty"],
        }
        response = requests.post(self.URI, headers=self.headers, json=request, verify=False)
        if response.status_code == 200:
            result_raw = response.json()
            result = result_raw["choices"][0]["text"]
            return result
        else:
            return default_answer

    def tokens_count(self, text: str):
        return len(text)

    def get_model_list(self):
        pass

    def load_model(self, model_file: str):
        pass
