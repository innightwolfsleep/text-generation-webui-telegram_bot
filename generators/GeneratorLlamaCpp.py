from llama_cpp import Llama
import os


class Generator:
    #  Place where path to LLM file stored
    llm: Llama = None
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = True  # if preset changing allowed.

    def __init__(self, model_path: str, n_ctx=4096, seed=0, n_gpu_layers=0):
        self.n_ctx = n_ctx
        self.seed = seed
        self.n_gpu_layers = n_gpu_layers
        self.llm = Llama(model_path=model_path, n_ctx=n_ctx, seed=seed, n_gpu_layers=n_gpu_layers)

    def get_answer(self,
                   prompt,
                   generation_params,
                   eos_token,
                   stopping_strings,
                   default_answer: str,
                   turn_template='',
                   **kwargs):
        # Preparing, add stopping_strings
        answer = default_answer

        try:
            answer = self.llm.create_completion(
                prompt=prompt,
                temperature=generation_params["temperature"],
                top_p=generation_params["top_p"],
                top_k=generation_params["top_k"],
                repeat_penalty=generation_params["repetition_penalty"],
                stop=stopping_strings,
                max_tokens=generation_params["max_new_tokens"],
                echo=True)
            answer = answer["choices"][0]["text"].replace(prompt, "")
        except Exception as exception:
            print("generator_wrapper get answer error ", exception)
        return answer

    def tokens_count(self, text: str):
        return len(self.llm.tokenize(text.encode(encoding="utf-8", errors="strict")))

    def get_model_list(self):
        bins = []
        for i in os.listdir("../models"):
            if i.endswith(".bin"):
                bins.append(i)
        return bins

    def load_model(self, model_file: str):
        with open("models\\" + model_file, "r") as model:
            self.llm: Llama = Llama(model_path=model.read(), n_ctx=self.n_ctx, seed=self.seed)
