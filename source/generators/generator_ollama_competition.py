import json
import random
import requests

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator


class Generator(AbstractGenerator):
    model_change_allowed = True  # Whether model changing is allowed without stopping.
    preset_change_allowed = True  # Whether preset file changing is allowed.

    def __init__(
        self,
        model_path="llama",  # Default Ollama API endpoint
        n_ctx=2048,
        seed=0,
        n_gpu_layers=0,
    ):
        self.model = model_path
        self.n_ctx = n_ctx
        self.headers = {"Content-Type": "application/json"}
        self.URI = "http://127.0.0.1:11434/api/generate"  # Fallback to default Ollama API endpoint
        self.last_token_count = 0  # Внутренняя переменная для хранения количества токенов

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
        # Prepare the request payload for Ollama API
        request = {
            "model": self.model,  # Specify the model to use (e.g., llama3)
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "system": "",
            "template": "",
            "options": {
                "temperature": generation_params["temperature"],
                "top_p": generation_params["top_p"],
                "top_k": generation_params["top_k"],
                "num_ctx": self.n_ctx,
                "num_predict": generation_params["max_new_tokens"],
                "seed": random.randint(0, 1000),  # Random seed for variability
                "stop": stopping_strings
            },
        }
        # Send the request to Ollama API
        response = requests.post(self.URI, json=request, headers=self.headers)
        if response.status_code == 200:
            # Ollama returns a stream of responses, so we need to collect all parts
            full_response = ""
            token_count = 0  # Счетчик токенов для текущей генерации

            for line in response.iter_lines():
                if line:
                    decoded_line = json.loads(line.decode("utf-8"))
                    full_response += decoded_line.get("response", "")
                    token_count = decoded_line.get("eval_count", 0)  # Обновляем количество токенов

            # Сохраняем количество токенов во внутренней переменной
            self.last_token_count = token_count

            return full_response
        else:
            # Return the default answer if the request fails
            self.last_token_count = 0  # Сбрасываем счетчик токенов в случае ошибки
            return default_answer

    def tokens_count(self, text: str = None):
        # NEED TO BE REWORKED: let ollama check and truncate text
        return 1

    def get_model_list(self):
        # Fetch the list of available models from Ollama
        response = requests.get("http://127.0.0.1:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [model["name"] for model in models]
        return []

    def load_model(self, model_file: str):
        self.model = model_file
        return True
