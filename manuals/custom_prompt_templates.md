If model uses custom prompt template - you needed to add this chat template to config file

There is some examples:


Will be added to readme later... 


empty template
```json
	"context_prompt_begin": "",
	"context_prompt_end": "",
	"user_prompt_begin": "",
	"user_prompt_end": "",
	"bot_prompt_begin": "",
	"bot_prompt_end": "",
```

ChatML
```
<|im_start|>system
{context}
<|im_end|>
<|im_start|>
{prompt}
<|im_end|>
<|im_start|>
{answer}
<|im_end|>
```
```json
	"context_prompt_begin": "<|im_start|>system\n",
	"context_prompt_end": "<|im_end|>",
	"user_prompt_begin": "<|im_start|>\n",
	"user_prompt_end": "<|im_end|>",
	"bot_prompt_begin": "<|im_start|>\n",
	"bot_prompt_end": "<|im_end|>",
```


Llama 2
```
[INST] <<SYS>>
{context}
<</SYS>>
[/INST]
[INST]
{prompt}
[/INST]
{answer}
```
```json
	"context_prompt_begin": "[INST] <<SYS>>\n",
	"context_prompt_end": "<</SYS>>",
	"user_prompt_begin": "[INST]\n",
	"user_prompt_end": "[/INST]",
	"bot_prompt_begin": "",
	"bot_prompt_end": "",
```

LimaRP-Alpaca
```
### Instruction:
Play the role of Character. You must engage in a roleplaying chat with User below this line. Do not write dialogues and narration for User. Character should respond with messages of medium length.
{context}
### Input:
{prompt}
### Response:
{answer}
```
```json
	"context_prompt_begin": "### Instruction:\nPlay the role of Character. You must engage in a roleplaying chat with User below this line. Do not write dialogues and narration for User. Character should respond with messages of medium length.\n",
	"context_prompt_end": "",
	"user_prompt_begin": "### Input:\n",
	"user_prompt_end": "\n",
	"bot_prompt_begin": "### Response:\n",
	"bot_prompt_end": "\n",
```

Zephyr 
```
<|system|>
{context}
</s>
<|user|>
{prompt}</s>
<|assistant|>
{answer}
</s>
```
```json
	"context_prompt_begin": "<|system|>\n",
	"context_prompt_end": "</s>",
	"user_prompt_begin": "<|user|>\n",
	"user_prompt_end": "</s>",
	"bot_prompt_begin": "<|assistant|>\n",
	"bot_prompt_end": "</s>",
```
