import json
import random
import requests

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator


class Generator(AbstractGenerator):
    model_change_allowed = False  # Whether model changing is allowed without stopping.
    preset_change_allowed = False  # Whether preset file changing is allowed.

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
            "options": {
                "temperature": generation_params["temperature"],
                "top_p": generation_params["top_p"],
                "top_k": generation_params["top_k"],
                "num_ctx": self.n_ctx,
                "max_tokens": generation_params["max_new_tokens"],
                "seed": random.randint(0, 1000),  # Random seed for variability
                "raw": True,
                #"stop": stopping_strings,
            },
        }

        # Send the request to Ollama API
        response = requests.post(self.URI, json=request, headers=self.headers)

        if response.status_code == 200:
            # Ollama returns a stream of responses, so we need to collect all parts
            full_response = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = json.loads(line.decode("utf-8"))
                    full_response += decoded_line.get("response", "")

            return full_response
        else:
            # Return the default answer if the request fails
            return default_answer

    def tokens_count(self, text: str):
        # Simple token counting implementation (can be replaced with a proper tokenizer)
        return len(text)

    def get_model_list(self):
        # Fetch the list of available models from Ollama
        response = requests.get("http://127.0.0.1:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [model["name"] for model in models]
        return []

    def load_model(self, model_file: str):
        # Placeholder for loading a model (if needed)
        pass
