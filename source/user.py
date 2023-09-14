import json
from os.path import exists

import yaml
from pathlib import Path


class TelegramBotUser:
    """
    Class stored individual tg user info (history, message sequence, etc...) and provide some actions
    """

    default_messages_template = {  # dict of messages templates for various situations. Use _VAR_ replacement
        "mem_lost": "<b>MEMORY LOST!</b>\nSend /start or any text for new session.",  # refers to non-existing
        "retyping": "<i>_NAME2_ retyping...</i>",  # added when "regenerate button" working
        "typing": "<i>_NAME2_ typing...</i>",  # added when generating working
        "char_loaded": "_NAME2_ LOADED!\n_GREETING_ ",  # When new char loaded
        "preset_loaded": "LOADED PRESET: _OPEN_TAG__CUSTOM_STRING__CLOSE_TAG_",  # When new char loaded
        "model_loaded": "LOADED MODEL: _OPEN_TAG__CUSTOM_STRING__CLOSE_TAG_",  # When new char loaded
        "mem_reset": "MEMORY RESET!\n_GREETING_",  # When history cleared
        "hist_to_chat": "To load history - forward message to this chat",  # download history
        "hist_loaded": "_NAME2_ LOADED!\n_GREETING_\n\nLAST MESSAGE:\n_CUSTOM_STRING_",  # load history
    }

    def __init__(
        self,
        char_file="",
        name1="You",
        name2="Bot",
        context="",
        example="",
        language="en",
        silero_speaker="None",
        silero_model_id="None",
        turn_template="",
        greeting="Hello.",
    ):
        """Init User class with default attribute

        Args:
          name1: username
          name2: current character name
          context: context of conversation, example: "Conversation between Bot and You"
          greeting: just greeting message from bot
        """
        self.char_file: str = char_file
        self.name1: str = name1
        self.name2: str = name2
        self.context: str = context
        self.example: str = example
        self.language: str = language
        self.silero_speaker: str = silero_speaker
        self.silero_model_id: str = silero_model_id
        self.turn_template: str = turn_template
        self.user_in: list = []  # "user input history": [["Hi!","Who are you?"]], need for regenerate option
        self.history: list = []  # "history": [["Hi!", "Hi there!","Who are you?", "I am you assistant."]],
        self.msg_id: list = []  # "msg_id": [143, 144, 145, 146],
        self.greeting: str = greeting

    def truncate(self):
        """Truncate user history (minus one answer and user input)

        Returns:
            user_in: truncated user input string
            msg_id: truncated answer message id (to be deleted in chat)
        """
        msg_id = self.msg_id.pop()
        user_in = self.user_in.pop()
        self.history = self.history[:-2]
        return user_in, msg_id

    def truncate_only_history(self):
        """Truncate user history (but not message list, used for message regenerating)

        Returns:
            truncated user input string
        """
        user_in = self.user_in.pop()
        self.history = self.history[:-2]
        return user_in

    def reset(self):
        """Clear bot history and reset to default everything but language, silero and chat_file."""
        self.name1 = "You"
        self.name2 = "Bot"
        self.context = ""
        self.example = ""
        self.turn_template = ""
        self.user_in = []
        self.history = []
        self.msg_id = []
        self.greeting = "Hello."

    def to_json(self):
        """Convert user data to json string.

        Returns:
            user data as json string
        """
        return json.dumps(
            {
                "char_file": self.char_file,
                "name1": self.name1,
                "name2": self.name2,
                "context": self.context,
                "example": self.example,
                "language": self.language,
                "silero_speaker": self.silero_speaker,
                "silero_model_id": self.silero_model_id,
                "turn_template": self.turn_template,
                "user_in": self.user_in,
                "history": self.history,
                "msg_id": self.msg_id,
                "greeting": self.greeting,
            }
        )

    def from_json(self, json_data: str):
        """Convert json string data to internal variables of User class

        Args:
            json_data: user json data string

        Returns:
            True if success, otherwise False
        """
        data = json.loads(json_data)
        try:
            self.char_file = data["char_file"] if "char_file" in data else ""
            self.name1 = data["name1"] if "name1" in data else "You"
            self.name2 = data["name2"] if "name2" in data else "Bot"
            self.context = data["context"] if "context" in data else ""
            self.example = data["example"] if "example" in data else ""
            self.language = data["language"] if "language" in data else "en"
            self.silero_speaker = data["silero_speaker"] if "silero_speaker" in data else "None"
            self.silero_model_id = data["silero_model_id"] if "silero_model_id" in data else "None"
            self.turn_template = data["turn_template"] if "turn_template" in data else ""
            self.user_in = data["user_in"]
            self.history = data["history"]
            self.msg_id = data["msg_id"]
            self.greeting = data["greeting"] if "greeting" in data else "Hello."
            return True
        except Exception as exception:
            print("from_json", exception)
            return False

    def load_character_file(self, characters_dir_path: str, char_file: str):
        """Load char file.
        First, reset all internal user data to default
        Second, read char file as yaml or json and converts to internal User data

        Args:
            characters_dir_path: path to character dir
            char_file: name of char file

        Returns:
            True if success, otherwise False
        """
        self.reset()
        # Copy default user data. If reading will fail - return default user data
        try:
            # Try to read char file.
            char_file_path = Path(f"{characters_dir_path}/{char_file}")
            with open(char_file_path, "r", encoding="utf-8") as user_file:
                if char_file.split(".")[-1] == "json":
                    data = json.loads(user_file.read())
                else:
                    data = yaml.safe_load(user_file.read())
            #  load persona and scenario
            self.char_file = char_file
            if "user" in data:
                self.name1 = data["user"]
            if "bot" in data:
                self.name2 = data["bot"]
            if "you_name" in data:
                self.name1 = data["you_name"]
            if "char_name" in data:
                self.name2 = data["char_name"]
            if "name" in data:
                self.name2 = data["name"]
            if "turn_template" in data:
                self.turn_template = data["turn_template"]
            self.context = ""
            if "char_persona" in data:
                self.context += f"{self.name2}'s Persona: {data['char_persona'].strip()}\n"
            if "context" in data:
                self.context += f"{data['context'].strip()}\n"
            if "world_scenario" in data:
                self.context += f"Scenario: {data['world_scenario'].strip()}\n"
            if "personality" in data:
                self.context += f"Personality: {data['world_scenario'].strip()}\n"
            if "description" in data:
                self.context += f"Description: {data['world_scenario'].strip()}\n"
            #  add dialogue examples
            if "example_dialogue" in data:
                self.example = f"\n{data['example_dialogue'].strip()}\n"
            #  add char greeting
            if "char_greeting" in data:
                self.greeting = data["char_greeting"].strip()
            if "greeting" in data:
                self.greeting = data["greeting"].strip()
            self.context = self.replace_context_templates(self.context)
            self.greeting = self.replace_context_templates(self.greeting)
            self.example = self.replace_context_templates(self.example)
            self.msg_id = []
            self.user_in = []
            self.history = []
        except Exception as exception:
            print("load_char_json_file", exception)
        finally:
            return self

    def replace_context_templates(self, s: str) -> str:
        s = s.replace("{{char}}", self.name2)
        s = s.replace("{{user}}", self.name1)
        s = s.replace("<BOT>", self.name2)
        s = s.replace("<USER>", self.name1)
        return s

    def find_and_load_user_char_history(self, chat_id, history_dir_path: str):
        """Find and load user chat history. History files searched by file name template:
            chat_id + char_file + .json (new template versions)
            chat_id + name2 + .json (old template versions)

        Args:
            chat_id: user id
            history_dir_path: path to history dir

        Returns:
            True user history found and loaded, otherwise False
        """
        chat_id = str(chat_id)
        user_char_history_path = f"{history_dir_path}/{str(chat_id)}{self.char_file}.json"
        user_char_history_old_path = f"{history_dir_path}/{str(chat_id)}{self.name2}.json"
        if exists(user_char_history_path):
            return self.load_user_history(user_char_history_path)
        elif exists(user_char_history_old_path):
            return self.load_user_history(user_char_history_old_path)
        return False

    def load_user_history(self, file_path):
        """load history file data to User data

        Args:
            file_path: path to history file

        Returns:
            True user history loaded, otherwise False
        """
        try:
            if exists(file_path):
                with open(file_path, "r", encoding="utf-8") as user_file:
                    data = user_file.read()
                self.from_json(data)
                if self.char_file == "":
                    self.char_file = self.name2
            return True
        except Exception as exception:
            print(f"load_user_history: {exception}")
            return False

    def save_user_history(self, chat_id, history_dir_path="history"):
        """Save two history file "user + char + .json" and default user history files and return their path

        Args:
          chat_id: user chat_id
          history_dir_path: history dir path

        Returns:
          user_char_file_path, default_user_file_path
        """
        if self.char_file == "":
            self.char_file = self.name2
        user_data = self.to_json()
        user_char_file_path = Path(f"{history_dir_path}/{chat_id}{self.char_file}.json")
        with user_char_file_path.open("w", encoding="utf-8") as user_file:
            user_file.write(user_data)

        default_user_file_path = Path(f"{history_dir_path}/{chat_id}.json")
        with default_user_file_path.open("w", encoding="utf-8") as user_file:
            user_file.write(user_data)

        return str(user_char_file_path), str(default_user_file_path)
