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
        self.URI = "http://127.0.0.1:11434/api/chat"  # Fallback to default Ollama API endpoint
        self.last_token_count = 0  # Внутренняя переменная для хранения количества токенов

    def generate_answer(
            self,
            prompt,
            generation_params,
            eos_token,
            stopping_strings,
            default_answer,
            kwargs,
            turn_template="",
    ):
        # Prepare the request payload for Ollama API
        history = kwargs["history"]
        context = kwargs["context"]
        greeting = kwargs["greeting"]
        example = kwargs["example"]
        messages = [
            {"role": "system", "content": context},
            {"role": "system", "content": example},
            {"role": "assistant", "content": greeting},
        ]
        for m in history:
            if len(m["in"]) > 0:
                messages.append({"role": "user", "content": m["in"]})
            if len(m["out"]) > 0:
                messages.append({"role": "assistant", "content": m["out"]})

        request = {
            "model": self.model,  # Specify the model to use (e.g., llama3)
            "messages": messages,
            "role": "assistant",
            "stream": False,
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
            decoded_line = json.loads(response.content.decode("utf-8"))
            result = decoded_line['message']['content']
            return result
        else:
            # Return the default answer if the request fails
            self.last_token_count = 0  # Сбрасываем счетчик токенов в случае ошибки
            return default_answer

    def tokens_count(self, text: str = None):
        # NEED TO BE REWORKED: let ollama check and truncate text
        return 0

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
