from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        """
        Generates text based on the given prompt.
        Args:
            prompt: The input prompt for the LLM.
            **kwargs: Additional parameters for the LLM API call (e.g., temperature, max_tokens).
        Returns:
            The generated text response.
        """
        pass

    @abstractmethod
    def generate_json(self, prompt: str, schema: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Generates JSON output based on the given prompt and a JSON schema.
        The implementation should ensure the output adheres to the schema.
        Args:
            prompt: The input prompt for the LLM.
            schema: A dictionary representing the JSON schema the output should adhere to.
            **kwargs: Additional parameters for the LLM API call.
        Returns:
            A dictionary representing the generated JSON response.
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the name of the LLM model being used."""
        pass
