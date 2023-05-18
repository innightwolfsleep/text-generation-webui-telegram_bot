from llama_cpp import Llama
import os

#  Place where path to LLM file stored
telegram_llm_model_path_file = "telegram_llm_model_path.txt"


n_ctx = 8196
seed = -1
#  Get llm_generator
with open(telegram_llm_model_path_file, "r") as model_path_file:
    data = model_path_file.read().rstrip()
    llm_generator: Llama = Llama(model_path=data, n_ctx=n_ctx, seed=seed, n_gpu_layers=2000)


def get_answer(
        prompt,
        generation_params,
        eos_token,
        stopping_strings,
        default_answer,
        turn_template='',
        **kwargs):
    answer = default_answer
    try:
        answer = llm_generator.create_completion(
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


def tokens_count(text: str):
    return len(llm_generator.tokenize(text.encode(encoding="utf-8", errors="strict")))


def get_model_list():
    bins = []
    for i in os.listdir("models"):
        if i.endswith(".bin"):
            bins.append(i)
    return bins


def load_model(model_file: str):
    with open("models\\" + model_file, "r") as model:
        llm_generator: Llama = Llama(model_path=model.read(), n_ctx=n_ctx, seed=seed)
