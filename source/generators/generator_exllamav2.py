from source.generators.abstract_generator import AbstractGenerator
import os, sys, random
import torch
from typing import List

sys.path.append(os.path.join(os.path.split(__file__)[0], "exllamav2"))

from exllamav2 import (
    ExLlamaV2,
    ExLlamaV2Config,
    ExLlamaV2Cache,
    ExLlamaV2Tokenizer,
)

from exllamav2.generator import ExLlamaV2BaseGenerator, ExLlamaV2Sampler


class Generator(AbstractGenerator):
    #  Place where path to LLM file stored
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = False  # if preset_file changing allowed.

    def __init__(self, model_path: str, n_ctx=4096, seed=0, n_gpu_layers=0):
        self.model_directory = model_path

        self.config = ExLlamaV2Config()
        self.config.model_dir = self.model_directory
        self.config.prepare()

        self.model = ExLlamaV2(self.config)

        self.cache = ExLlamaV2Cache(self.model, lazy=True)
        self.model.load_autosplit(self.cache)

        self.tokenizer = ExLlamaV2Tokenizer(self.config)

        # Initialize generator

        self.generator = ExLlamaV2BaseGenerator(self.model, self.cache, self.tokenizer)

        # Generate some text

        self.settings = ExLlamaV2Sampler.Settings()
        self.settings.temperature = 0.85
        self.settings.top_k = 50
        self.settings.top_p = 0.8
        self.settings.token_repetition_penalty = 1.15
        self.settings.disallow_tokens(self.tokenizer, [self.tokenizer.eos_token_id])

    def generate_answer(
        self, prompt, generation_params, eos_token, stopping_strings, default_answer: str, turn_template="", **kwargs
    ):
        # Preparing, add stopping_strings
        answer = default_answer

        try:
            # Configure generator
            self.settings.token_repetition_penalty_max = generation_params["repetition_penalty"]
            self.settings.temperature = generation_params["temperature"]
            self.settings.top_p = generation_params["top_p"]
            self.settings.top_k = generation_params["top_k"]
            self.settings.typical = generation_params["typical_p"]
            # Produce a simple generation
            answer = self.generate_custom(
                prompt,
                stopping_strings=stopping_strings,
                gen_settings=self.settings,
                num_tokens=generation_params["max_new_tokens"],
            )
            answer = answer[len(prompt) :]

        except Exception as exception:
            print("generator_wrapper get answer error ", str(exception) + str(exception.args))
        return answer

    def generate_custom(
        self,
        prompt: str or list,
        gen_settings: ExLlamaV2Sampler.Settings,
        num_tokens: int,
        stopping_strings: List,
        seed=None,
        token_healing=False,
        encode_special_tokens=False,
        decode_special_tokens=False,
        loras=None,
    ):
        # Apply seed

        if seed is not None:
            random.seed(seed)

        # Tokenize input and produce padding mask if needed

        batch_size = 1 if isinstance(prompt, str) else len(prompt)
        ids = self.tokenizer.encode(prompt, encode_special_tokens=encode_special_tokens)

        overflow = ids.shape[-1] + num_tokens - self.model.config.max_seq_len
        if overflow > 0:
            ids = ids[:, overflow:]

        mask = self.tokenizer.padding_mask(ids) if batch_size > 1 else None

        # Prepare for healing

        unhealed_token = None
        if ids.shape[-1] < 2:
            token_healing = False
        if token_healing:
            unhealed_token = ids[:, -1:]
            ids = ids[:, :-1]

        # Process prompt and begin gen

        self._gen_begin_base(ids, mask, loras)

        # Begin filters

        id_to_piece = self.tokenizer.get_id_to_piece_list()
        if unhealed_token is not None:
            unhealed_token_list = unhealed_token.flatten().tolist()
            heal = [id_to_piece[x] for x in unhealed_token_list]
        else:
            heal = None
        gen_settings.begin_filters(heal)

        # Generate tokens

        for i in range(num_tokens):
            logits = (
                self.model.forward(self.sequence_ids[:, -1:], self.cache, input_mask=mask, loras=loras).float().cpu()
            )
            token, _, eos = ExLlamaV2Sampler.sample(
                logits, gen_settings, self.sequence_ids, random.random(), self.tokenizer, prefix_token=unhealed_token
            )
            self.sequence_ids = torch.cat([self.sequence_ids, token], dim=1)
            gen_settings.feed_filters(token)

            unhealed_token = None
            # check stopping string
            text = self.tokenizer.decode(self.sequence_ids, decode_special_tokens=decode_special_tokens)
            if isinstance(prompt, str):
                text = text[0]
            for stopping in stopping_strings:
                if text.endswith(stopping):
                    text = text[: -len(stopping)]
                    return text
            if eos:
                break

        # Decode

        text = self.tokenizer.decode(self.sequence_ids, decode_special_tokens=decode_special_tokens)

        if isinstance(prompt, str):
            text = text[0]
        return text

    def _gen_begin_base(self, input_ids, mask=None, loras=None):
        self.cache.current_seq_len = 0
        self.model.forward(input_ids[:, :-1], self.cache, input_mask=mask, preprocess_only=True, loras=loras)

        self.sequence_ids = input_ids.clone()
        self.sequence_ids = input_ids

    def tokens_count(self, text: str):
        encoded = self.tokenizer.encode(text)
        return len(encoded[0])

    def get_model_list(self):
        bins = []
        for i in os.listdir("../../models"):
            if i.endswith(".bin"):
                bins.append(i)
        return bins

    def load_model(self, model_file: str):
        return None
