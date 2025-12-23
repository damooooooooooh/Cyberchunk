from abc import ABC, abstractmethod
from typing import List

class Embedder(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """
        Embeds a single piece of text.
        Args:
            text: The text to embed.
        Returns:
            A list of floats representing the embedding vector.
        """
        pass

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of texts.
        Args:
            texts: A list of texts to embed.
        Returns:
            A list of embedding vectors, where each vector is a list of floats.
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the name of the embedding model being used."""
        pass
