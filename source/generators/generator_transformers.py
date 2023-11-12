import transformers
from transformers import AutoTokenizer

try:
    from extensions.telegram_bot.source.generators.abstract_generator import AbstractGenerator
except ImportError:
    from source.generators.abstract_generator import AbstractGenerator


class Generator(AbstractGenerator):
    model_change_allowed = False  # if model changing allowed without stopping.
    preset_change_allowed = True  # if preset_file changing allowed.

    def __init__(self, model_path, n_ctx=2048, seed=0, n_gpu_layers=0):
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.pipeline = transformers.pipeline(
            "text-generation",
            model=model_path,
            device_map="auto",
        )

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
        if "max_tokens" in generation_params:
            max_tokens = generation_params["max_tokens"]
        if "temperature" in generation_params:
            temperature = generation_params["temperature"]
        top_k = 10
        if "top_k" in generation_params:
            top_k = generation_params["top_k"]

        sequences = self.pipeline(
            prompt,
            do_sample=True,
            top_k=top_k,
            num_return_sequences=1,
            eos_token_id=self.tokenizer.eos_token_id,
            max_length=200,
        )
        answer = ""
        for seq in sequences:
            answer += seq["generated_text"]
            print(f"Result: {seq['generated_text']}")
        return answer

    def tokens_count(self, text: str):
        return 0

    def get_model_list(self):
        pass

    def load_model(self, model_file: str):
        pass
