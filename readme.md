Extension connecting text-generator to telegram bot api.
-
![Image1](https://github.com/innightwolfsleep/storage/raw/main/textgen_telegram.PNG)

This is extension for [oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui) providing cai-chat like telegram bot interface.

REQUIREMENTS:
- [oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui)
- python-telegram-bot==13.15
- pyyaml _(already in text-generation-webui requirements)_
- deep-translator _(already in text-generation-webui requirements)_

HOW TO INSTALL:
1) clone this repo to "text-generation-webui\extensions"
```
cd text-generation-webui
git clone https://github.com/innightwolfsleep/text-generation-webui-telegram_bot extensions\telegram_bot
```
2) install "python-telegram-bot==13.15" module to your textgen environment. (run **cmd_windows.bat** or **cmd_linux.sh** and send run **pip install -r extensions\telegram_bot\requirements.txt**)

HOW TO USE:
1) add your bot token to "text-generation-webui\extensions\telegram_bot\telegram_token.txt" (ask https://t.me/BotFather how to get token)
2) run server.py with "--extensions telegram_bot"

FEATURES:
- chat and notebook modes
- session for all users are separative (by chat_id)
- local session history - conversation won't be lost if server restarts. Separated history between users and chars.
- chat action "typing" during generating
- buttons: continue previous message, regenerate last message, remove last messages from history, reset history button, new char loading menu
- you can load new characters from text-generation-webui\characters with button
- you can load new model during conversation with button
- chatting "#" or "+" prefix for impersonate: "#You" or "+Castle guard" or "#Alice thoughts about me"
- "!" or "-" prefix to replace last bot message
- "++" prefix permanently replace bot name during chat (switch conversation to another character)
- save/load history in chat by downloading/forwarding to chat .json file
- integrated auto-translate (you can set model/user language parameter) 
- voice generating ([silero](https://github.com/snakers4/silero-models)), en and ru variants
- translation_as_hidden_text option in .cfg - if you want to learn english with bot)))
- telegram_users.txt - list of permitted users (if empty - permit for all)
- antiflood - one message per 15 sec from one user limit



CONFIGURATION:

telegram_config.cfg
```
  bot_mode=admin  
	  - admin - bot answer for everyone in chat-like mode. All buttons, include settings-for-all are avariable for everyone. (Default)
	  - chat - bot answer for everyone in chat-like mode. All buttons, exclude settings-for-all are avariable for everyone. (Recommended for chatting)
	  - chat-restricted - same as chat, but user can't change default character
	  - persona - same as chat-restricted, but reset/regenerate/delete message are unavailable too. 
	  - notebook - notebook-like mode. Restriction like in chat mode.
	  - query - same as notebook, but without history. Each question fo bot is like new convrsation.
  characters_dir_path=characters
  default_char=Example.yaml
  presets_dir_path=presets
  default_preset=Shortwave.yaml
  model_lang=en
  user_lang=en
  html_tag_open=\<pre\>
  html_tag_close=\<\/pre\>
  history_dir_path=extensions/telegram_bot/history
  token_file_path=extensions/telegram_bot/telegram_token.txt
  admins_file_path=extensions/telegram_bot/telegram_admins.txt
  users_file_path=extensions/telegram_bot/telegram_users.txt
  stopping_strings=<END>,<START>,end{code}
  eos_token=None
  translation_as_hidden_text=on

```
