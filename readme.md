#Extension connecting llm_python to telegram bot api.
-
![Image1](https://github.com/innightwolfsleep/storage/raw/main/textgen_telegram.PNG)

Providing chat like telegram bot interface with [abetlen/llm_python](https://github.com/abetlen/llm_python), [langchain](https://pypi.org/project/langchain/) or transformers (tbc) 

REQUIREMENTS:
- python-telegram-bot==13.15
- pyyaml
- deep-translator==1.9.2
- llama-cpp-python

HOW TO INSTALL:
1) clone this repo to "text-generation-webui\extensions"
```
cd text-generation-webui
git clone https://github.com/innightwolfsleep/llm_telegram_bot 
```
2) install requirements. 
```
pip install -r llm_telegram_bot\requirements.txt
```

HOW TO USE:
1) add your bot token to llm_telegram_bot/telegram_token.txt (ask https://t.me/BotFather how to get token)
2) add your model bin file to llm_telegram_bot/models
3) write path to your bin model file in telegram_config.cfg - model_path
2) run "python llm_telegram_bot/main.py"

FEATURES:
- chat and notebook modes
- session for all users are separative (by chat_id)
- local session history - conversation won't be lost if server restarts. Separated history between users and chars.
- nice "X typing" during generating (users will not think that bot stucking)
- buttons: continue previous message, regenerate last message, remove last messages from history, reset history button, new char loading menu
- you can load new characters from text-generation-webui\characters with button
- you can load new model during conversation with button
- chatting # prefix for impersonate: "#You" or "#Castle guard" or "#Alice thoughts about me"
- "!" prefix to replace last bot message
- "++" prefix permanently replace bot name during chat (switch conversation to another character)
- save/load history in chat by downloading/forwarding to chat .json file
- integrated auto-translate (you can set model/user language parameter) 
- voice generating ([silero](https://github.com/snakers4/silero-models)), en and ru variants
- translation_as_hidden_text option in .cfg - if you want to learn english with bot)))
- telegram_users.txt - list of permitted users (if empty - permit for all)
- antiflood - one message per 15 sec from one user


CONFIGURATION:

telegram_config.cfg
```
telegram_config.cfg
    bot_mode=admin  
        specific bot mode. admin for personal use
            - admin - bot answer for everyone in chat-like mode. All buttons, include settings-for-all are avariable for everyone. (Default)
            - chat - bot answer for everyone in chat-like mode. All buttons, exclude settings-for-all are avariable for everyone. (Recommended for chatting)
            - chat-restricted - same as chat, but user can't change default character
            - persona - same as chat-restricted, but reset/regenerate/delete message are unavailable too. 
            - notebook - notebook-like mode. Prefixes wont added automaticaly, only "\n" separate user and bot messages. Restriction like chat mode.
            - query - same as notebook, but without history. Each question for bot is like new convrsation withot influence of previous questions
    generator_script=GeneratorLlamaCpp
        name of generator script (generators folder):
            - GeneratorLlamaCpp - based on llama-cpp-python, recommended
            - GeneratorLangchainLlamaCpp - based in langchain+llama
            - GeneratorTransformers - based on transformers, untested
            - GeneratorTextGenerationWebui - module to integrate in oobabooga/text-generation-webui 
            - GeneratorTextGenerationWebuiApi - use oobabooga/text-generation-webui API extension
    model_path=models\llama-13b.ggml.q4_0.bin
        path to model .bin file
	characters_dir_path=characters
	default_char=Example.yaml
		default cahracter and path to cahracters folder
	presets_dir_path=presets
	default_preset=Shortwave.yaml
		default generation preset and path to preset folder
	model_lang=en
	user_lang=en
		default model and user language. User language can be switched by users, individualy.
	html_tag_open=<pre>
	html_tag_close=</pre>
		tags for bot answers in tg. By default - preformatted text (pre)
	history_dir_path=history
		directory for users history
	token_file_path=telegram_token.txt
		bot token. Ask https://t.me/BotFather
	admins_file_path=telegram_admins.txt
		users whos id's in admins_file switched to admin mode and can choose settings-for-all (generating settings and model)
	users_file_path=telegram_users.txt
		if just one id in users_file - bot will ignore all users except this id (id's). Even admin will be ignored
	stopping_strings=<END>,<START>,end{code}
	eos_token=None
		generating settings
	translation_as_hidden_text=on
		if "on" and model/user lang not the same - translation will be writed under spoiler. If "off" - translation without spoiler, no original text in message.

telegram_admins.txt
	list of users id who forced to admin mode. 

telegram_users.txt
	list og users id (or groups id) who permitted interact with bot. If empty - everyone permitted

telegram_token.txt
	telegram bot token

```
