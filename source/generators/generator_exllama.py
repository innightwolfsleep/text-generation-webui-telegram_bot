try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator
import os, glob, sys
import torch
from typing import List

sys.path.append(os.path.join(os.path.split(__file__)[0], "exllama"))
from source.generators.exllama.model import ExLlama, ExLlamaCache, ExLlamaConfig
from source.generators.exllama.tokenizer import ExLlamaTokenizer
from source.generators.exllama.generator import ExLlamaGenerator


class Generator(AbstractGenerator):
    #  Place where path to LLM file stored
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = True  # if preset_file changing allowed.

    def __init__(self, model_path: str, n_ctx=4096, seed=0, n_gpu_layers=0):
        self.n_ctx = n_ctx
        self.seed = seed
        self.n_gpu_layers = n_gpu_layers
        self.model_directory = model_path

        # Locate files we need within that directory
        self.tokenizer_path = os.path.join(self.model_directory, "tokenizer.model")
        self.model_config_path = os.path.join(self.model_directory, "config.json")
        self.st_pattern = os.path.join(self.model_directory, "model.safetensors")
        self.model_path = glob.glob(self.st_pattern)
        # Create config, model, tokenizer and generator

        self.ex_config = ExLlamaConfig(self.model_config_path)  # create config from config.json
        self.ex_config.llm_path = self.model_path  # supply path to model weights file
        self.ex_config.max_seq_len = n_ctx
        self.ex_config.max_input_len = n_ctx
        self.ex_config.max_attention_size = n_ctx**2
        self.model = ExLlama(self.ex_config)  # create ExLlama instance and load the weights

        self.tokenizer = ExLlamaTokenizer(self.tokenizer_path)  # create tokenizer from tokenizer model file

        self.cache = ExLlamaCache(self.model, max_seq_len=n_ctx)  # create cache for inference
        self.generator = ExLlamaGenerator(self.model, self.tokenizer, self.cache)  # create generator

    def generate_answer(
        self, prompt, generation_params, eos_token, stopping_strings, default_answer: str, turn_template="", **kwargs
    ):
        # Preparing, add stopping_strings
        answer = default_answer

        try:
            # Configure generator
            self.generator.disallow_tokens([self.tokenizer.eos_token_id])
            self.generator.settings.token_repetition_penalty_max = generation_params["repetition_penalty"]
            self.generator.settings.temperature = generation_params["temperature"]
            self.generator.settings.top_p = generation_params["top_p"]
            self.generator.settings.top_k = generation_params["top_k"]
            self.generator.settings.typical = generation_params["typical_p"]
            # random seed set
            random_data = os.urandom(4)
            random_seed = int.from_bytes(random_data, byteorder="big")
            torch.manual_seed(random_seed)
            torch.cuda.manual_seed(random_seed)
            # Produce a simple generation
            answer = self.generate_custom(
                prompt, stopping_strings=stopping_strings, max_new_tokens=generation_params["max_new_tokens"]
            )
            answer = answer[len(prompt) :]
        except Exception as exception:
            print("generator_wrapper get answer error ", str(exception) + str(exception.args))
        return answer

    def generate_custom(self, prompt, stopping_strings: List, max_new_tokens=128):
        self.generator.end_beam_search()

        ids, mask = self.tokenizer.encode(prompt, return_mask=True, max_seq_len=self.model.config.max_seq_len)
        self.generator.gen_begin(ids, mask=mask)

        max_new_tokens = min(max_new_tokens, self.model.config.max_seq_len - ids.shape[1])

        eos = torch.zeros((ids.shape[0],), dtype=torch.bool)
        for i in range(max_new_tokens):
            token = self.generator.gen_single_token(mask=mask)
            for j in range(token.shape[0]):
                if token[j, 0].item() == self.tokenizer.eos_token_id:
                    eos[j] = True
            text = self.tokenizer.decode(
                self.generator.sequence[0] if self.generator.sequence.shape[0] == 1 else self.generator.sequence
            )
            # check stopping string
            for stopping in stopping_strings:
                if text.endswith(stopping):
                    text = text[: -len(stopping)]
                    return text
            if eos.all():
                break

        text = self.tokenizer.decode(
            self.generator.sequence[0] if self.generator.sequence.shape[0] == 1 else self.generator.sequence
        )
        return text

    def tokens_count(self, text: str):
        encoded = self.tokenizer.encode(text, max_seq_len=20480)
        return len(encoded[0])

    def get_model_list(self):
        bins = []
        for i in os.listdir("../../models"):
            if i.endswith(".bin"):
                bins.append(i)
        return bins

    def load_model(self, model_file: str):
        return None
