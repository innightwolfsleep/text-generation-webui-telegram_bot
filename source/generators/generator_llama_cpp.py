import os

from llama_cpp import Llama

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator


class Generator(AbstractGenerator):
    #  Place where path to LLM file stored
    llm: Llama = None
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = True  # if preset_file changing allowed.

    def __init__(self, model_path: str, n_ctx=4096, seed=0, n_gpu_layers=0):
        self.n_ctx = n_ctx
        self.seed = seed
        self.n_gpu_layers = n_gpu_layers
        self.llm = Llama(model_path=model_path, n_ctx=n_ctx, seed=seed, n_gpu_layers=n_gpu_layers)

    def generate_answer(
        self, prompt, generation_params, eos_token, stopping_strings, default_answer: str, turn_template="", **kwargs
    ):
        # Preparing, add stopping_strings
        answer = default_answer

        try:
            answer = self.llm.create_completion(
                prompt=prompt,
                max_tokens=generation_params["max_new_tokens"],
                temperature=generation_params["temperature"],
                top_p=generation_params["top_p"],
                echo=True,
                stop=stopping_strings,
                repeat_penalty=generation_params["repetition_penalty"],
                top_k=generation_params["top_k"],
                mirostat_mode=generation_params["mirostat_mode"],
                mirostat_tau=generation_params["mirostat_tau"],
                mirostat_eta=generation_params["mirostat_eta"],
            )
            answer = answer["choices"][0]["text"].replace(prompt, "")
        except Exception as exception:
            print("generator_wrapper get answer error ", exception)
        return answer

    def tokens_count(self, text: str):
        return len(self.llm.tokenize(text.encode(encoding="utf-8", errors="strict")))

    def get_model_list(self):
        bins = []
        for i in os.listdir("../../models"):
            if i.endswith(".bin"):
                bins.append(i)
        return bins

    def load_model(self, model_file: str):
        with open(os.path.normpath("models\\" + model_file), "r") as model:
            self.llm: Llama = Llama(model_path=model.read(), n_ctx=self.n_ctx, seed=self.seed)
