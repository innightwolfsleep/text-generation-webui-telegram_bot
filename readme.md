#Extension connecting text-generator to telegram bot api.
-

REQUIREMENTS:
- python-telegram-bot==13.15
- pyyaml

HOW TO USE:
1) place to your bot token to "text-generation-webui\extensions\telegram_bot\telegram_token.txt"
2) run server.py with "--extensions telegram_bot"

FEATURES:
- chat and notebook modes
- session for all users are separative (by chat_id)
- local session history - conversation won't be lost if server restarts. Separated history between users and chars.
- nice "X typing" during generating (users will not think that bot is stuck)
- regenerate last message, remove last messages from history, reset history button, continue previous message
- you can load new characters from text-generation-webui\characters with "/loadX" command!!!
- chatting # prefix for impersonate: "#You" or "#Castle guard" or "#Alice thoughts about me"


TBC:
- replace "X typing" by yield from generator
- group chat mode (need to be tested, does current workflow is ok?)
