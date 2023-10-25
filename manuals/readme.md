This is manual about telegram buttons, prefixes and functions.

# Start conversation:
After /start interaction with bot first time, bot sends you default char greeting with option menu:

![Image1](https://raw.githubusercontent.com/innightwolfsleep/llm_telegram_bot/main/manuals/telegram_bot_start_option.PNG)

To get first answer just write something (but not single emoji or sticker)

![Image1](https://raw.githubusercontent.com/innightwolfsleep/llm_telegram_bot/main/manuals/telegram_bot_message.PNG)

Here you are! Answer with message buttons!


# Buttons:

![Image1](https://raw.githubusercontent.com/innightwolfsleep/llm_telegram_bot/main/manuals/telegram_bot_message_narrow.png)

Message buttons. There can be only one message in conversation with "message buttons", so message keyboard always moves to last bot message.
- "▶Next" - this button call next message from bot, like an empty input from you.
- "➡Continue" - seems like Next button, but call not new message - but continuing of current.
- "⬅Del word" - delete last word in current message, if you want "correct" your character answer.
- "♻Regenerate" - last message will be generated again, so result can be different. 
- "✖Cutoff" - last message to be deleted. Message keyboard moves to previous bot answer.
- "⚙Options" - call option menu

![Image1](https://raw.githubusercontent.com/innightwolfsleep/llm_telegram_bot/main/manuals/telegram_bot_start_option_narrow.PNG)

Option buttons can be called in any moment, multiply times.
- "💾Save" - save whole conversation and some settings to .json file and send in chat. Forward this json file to chat to load old conversation.
- "🎭Chars" - show list of available characters. Click and enjoy!
- "⚠Reset" - if current conversation goes wrong - you can reset it and get greeting again.
- "🇯🇵Language" - you can choose language to translate. Translation will be under spoilers (this can be changed in config)
- "🔈Voice" - you can switch on voice generating and choose voices (man or woman)! 
- "🔧Presets" - if you are admin - you can choose generating preset (applied for all users)
- "🔨Model" - if you are admin - you can switch generator model (if available for generator type, applied for all users) 
- "❌Close" - just delete this option message to keep chat clear.

# Prefixes:
- "+", "#" [name or situation] - change character name for next message. 
- "++" [new name] - permanently change character name 
- "-", "!" [corrected message] - replace last bot message on yours. If you wanna force switch conversation direction.
- "📷","📸","📹","🎥","📽" [name or situation] - call image of something/someone. (Stable diffusion with --api should be run)

# How to maximize your conversation?
- Use prefixes
- Use "Regenerate", "Cutoff" and "Next" buttons if conversation goes wrong way! 
- Do not forget about save/load.
