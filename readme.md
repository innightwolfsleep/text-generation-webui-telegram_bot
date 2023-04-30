#Extension connecting text-generator to telegram bot api.
-
![Image1](https://github.com/innightwolfsleep/storage/raw/main/textgen_telegram.PNG)

This is extension for [oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui) providing cai-chat like telegram bot interface.

REQUIREMENTS:
- python-telegram-bot==13.15
- pyyaml

HOW TO INSTALL:
1) clone this repo to "text-generation-webui\extensions"
```
cd text-generation-webui
git clone https://github.com/innightwolfsleep/text-generation-webui-telegram_bot extensions\telegram_bot
```
2) install "python-telegram-bot==13.15" module to your textgen environment. (Easiest way add in start script "**call pip install -r extensions\telegram_bot\requirements.txt**" before "python webui.py")

HOW TO USE:
1) add your bot token to "text-generation-webui\extensions\telegram_bot\telegram_token.txt" (ask https://t.me/BotFather how to get token)
2) run server.py with "--extensions telegram_bot"

FEATURES:
- chat and notebook modes
- session for all users are separative (by chat_id)
- local session history - conversation won't be lost if server restarts. Separated history between users and chars.
- nice "X typing" during generating (users will not think that bot stucking)
- buttons: continue previous message, regenerate last message, remove last messages from history, reset history button, new char loading menu
- you can load new characters from text-generation-webui\characters with "/load" command!!!
- you can load new model during conversation with /models 
- chatting # prefix for impersonate: "#You" or "#Castle guard" or "#Alice thoughts about me"
- "!" prefix to replace last bot message
- save/load history in chat by downloading/forwarding to chat .json file
- integrated auto-translate (you can set model/user language parameter) 

TBC:
- replace "X typing" by yield from generator
- group chat mode (need to be tested, does current workflow is ok?)
- migrate to aiogram or not?