# Default error messages
GENERATOR_FAIL = "<GENERATION FAIL>"
GENERATOR_EMPTY_ANSWER = "<EMPTY ANSWER>"
UNKNOWN_TEMPLATE = "<UNKNOWN TEMPLATE>"
UNKNOWN_USER = "<UNKNOWN USER>"
# Various predefined data
MODE_ADMIN = "admin"
MODE_CHAT = "chat"
MODE_CHAT_R = "chat-restricted"
MODE_NOTEBOOK = "notebook"
MODE_PERSONA = "persona"
MODE_QUERY = "query"
BTN_CONTINUE = "Continue"
BTN_IMPERSONATE = "Impersonate"
BTN_NEXT = "Next"
BTN_IMPERSONATE_INIT = "InitialImpersonate"
BTN_NEXT_INIT = "InitialNext"
BTN_DEL_WORD = "Delete_one_word"
BTN_PREVIOUS = "Previous_message"
BTN_REGEN = "Regen"
BTN_CUTOFF = "Cutoff"
BTN_DELETE = "Delete"
BTN_RESET = "Reset"
BTN_DOWNLOAD = "Download"
BTN_LORE = "Context"
BTN_CHAR_LIST = "Chars_list"
BTN_CHAR_LOAD = "Chars_load"
BTN_MODEL_LIST = "Model_list"
BTN_MODEL_LOAD = "Model_load"
BTN_VOICE_LIST = "Voice_list"
BTN_VOICE_LOAD = "Voice_load"
BTN_PRESET_LIST = "Presets_list"
BTN_PRESET_LOAD = "Preset_load"
BTN_LANG_LIST = "Language_list"
BTN_LANG_LOAD = "Language_load"
BTN_OPTION = "options"
GET_MESSAGE = "message"
MSG_SEND = "send"
MSG_SYSTEM = "system"
MSG_DEL_LAST = "delete_last_message"
MSG_SD_API = "send_to_sd_api"
MSG_NOTHING_TO_DO = "nothing_to_do"
GENERATOR_MODE_IMPERSONATE = "/send_impersonated_message"
GENERATOR_MODE_NEXT = "/send_next_message"
GENERATOR_MODE_DEL_WORD = "/delete_word"
GENERATOR_MODE_REGENERATE = "/regenerate_message"
GENERATOR_MODE_CONTINUE = "/continue_last_message"

DEFAULT_MESSAGE_TEMPLATE = {  # dict of messages templates for various situations. Use _VAR_ replacement
    "mem_lost": "<b>MEMORY LOST!</b>\nSend /start or any text for new session.",  # refers to non-existing
    "retyping": "<i>_NAME2_ retyping...</i>",  # added when "regenerate button" working
    "typing": "<i>_NAME2_ typing...</i>",  # added when generating working
    "char_loaded": "_NAME2_ LOADED!\n_GREETING_ ",  # When new character_file loaded
    "preset_loaded": "LOADED PRESET: _OPEN_TAG__CUSTOM_STRING__CLOSE_TAG_",  # When new character_file loaded
    "model_loaded": "LOADED MODEL: _OPEN_TAG__CUSTOM_STRING__CLOSE_TAG_",  # When new character_file loaded
    "mem_reset": "MEMORY RESET!\n_GREETING_",  # When history cleared
    "hist_to_chat": "To load history - forward message to this chat",  # download history
    "hist_loaded": "_NAME2_ LOADED!\n_GREETING_\n\nLAST MESSAGE:\n_CUSTOM_STRING_",  # load history
}
