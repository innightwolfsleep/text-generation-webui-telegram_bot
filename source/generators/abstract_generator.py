from abc import ABC, abstractmethod
from typing import List, Dict


class AbstractGenerator(ABC):
    @property
    @abstractmethod
    def model_change_allowed(self) -> bool:
        """
        If True - model changing without restart allowed
        """
        pass

    @property
    @abstractmethod
    def preset_change_allowed(self) -> bool:
        """
        If True - preset_file changing without restart allowed
        """
        pass

    @abstractmethod
    def generate_answer(
        self,
        prompt: str,
        generation_params: Dict,
        eos_token: str,
        stopping_strings: List,
        default_answer: str,
        turn_template: str,
        **kwargs
    ) -> str:
        """
        Get llm answer
        """
        pass

    @abstractmethod
    def tokens_count(self, text: str) -> int:
        """
        get token count for text
        """
        pass

    @abstractmethod
    def get_model_list(self):
        """
        return list of available models
        """
        pass

    @abstractmethod
    def load_model(self, model_file: str):
        """
        Set new model
        """
        pass
