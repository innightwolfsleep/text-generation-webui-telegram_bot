import os

import langchain.text_splitter
from langchain import PromptTemplate, LLMChain
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.llms import LlamaCpp

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator

#  Place where path to LLM file stored
llm = None


# Callbacks support token-wise streaming


class Generator(AbstractGenerator):
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = True  # if preset_file changing allowed.

    def __init__(self, model_path, n_ctx=2048, seed=0, n_gpu_layers=0):
        callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])
        self.llm = LlamaCpp(
            model_path=model_path,
            n_ctx=n_ctx,
            callback_manager=callback_manager,
            verbose=True,
        )

    def generate_answer(
        self, prompt, generation_params, eos_token, stopping_strings, default_answer, turn_template="", **kwargs
    ):
        if "max_tokens" in generation_params:
            llm.max_tokens = generation_params["max_tokens"]
        if "temperature" in generation_params:
            llm.temperature = generation_params["temperature"]
        if "top_p" in generation_params:
            llm.top_p = generation_params["top_p"]
        if "top_k" in generation_params:
            llm.top_k = generation_params["top_k"]
        prompt_template = PromptTemplate(template="{prompt}", input_variables=["prompt"])
        llm.stop = stopping_strings
        llm_chain = LLMChain(prompt=prompt_template, llm=self.llm)
        answer = llm_chain.run(prompt)
        return answer

    def tokens_count(self, text: str):
        splitter = langchain.text_splitter.TokenTextSplitter()
        length = len(splitter.split_text(text))
        return length

    def get_model_list(
        self,
    ):
        bins = []
        for i in os.listdir("models"):
            if i.endswith(".bin"):
                bins.append(i)
        return bins

    def load_model(self, model_file: str):
        pass
