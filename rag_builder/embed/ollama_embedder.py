import requests
from typing import List, Dict, Any
from rag_builder.embed.embedder import Embedder

class OllamaEmbedder(Embedder):
    """Concrete implementation of Embedder for Ollama."""

    def __init__(self, endpoint: str, model: str):
        self._endpoint = f"{endpoint.rstrip('/')}/embeddings"
        self._model_name = model
        print(f"Initialized OllamaEmbedder with endpoint: {self._endpoint} and model: {self._model_name}")

    @property
    def model_name(self) -> str:
        return self._model_name

    def _call_ollama_api(self, text: str) -> List[float]:
        headers = {"Content-Type": "application/json"}
        data = {
            "model": self._model_name,
            "prompt": text,
            "options": {
                "num_ctx": 4096 # Assuming a reasonable context window for embeddings
            }
        }
        try:
            response = requests.post(self._endpoint, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            if "embedding" in result:
                return result["embedding"]
            else:
                raise ValueError(f"Ollama API response missing 'embedding' field: {result}")
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Ollama API request timed out after 60 seconds for model {self._model_name}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Error connecting to Ollama API at {self._endpoint}: {e}")
        except ValueError as e:
            raise ValueError(f"Failed to parse Ollama API response: {e}")

    def embed_text(self, text: str) -> List[float]:
        return self._call_ollama_api(text)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # Ollama's /api/embeddings endpoint typically processes one prompt at a time.
        # For bulk embedding, we iterate and call the single embed endpoint.
        # A more optimized solution might use a batching API if Ollama provides one,
        # or leverage async if performance is critical for large batches.
        embeddings = []
        for text in texts:
            embeddings.append(self.embed_text(text))
        return embeddings

if __name__ == '__main__':
    # Example usage - replace with your actual Ollama endpoint and model
    # Ensure Ollama server is running and model is available: ollama run nomic-embed-text
    OLLAMA_ENDPOINT = "https://chat.meshanised.xyz/ollama/api" # Use the user's provided endpoint
    OLLAMA_MODEL = "nomic-embed-text:latest" # Use the user's provided model

    try:
        ollama_embedder = OllamaEmbedder(endpoint=OLLAMA_ENDPOINT, model=OLLAMA_MODEL)
        
        test_text_single = "This is a test sentence for embedding."
        embedding_single = ollama_embedder.embed_text(test_text_single)
        print(f"Single embedding (first 5 values): {embedding_single[:5]}...")
        print(f"Embedding dimension: {len(embedding_single)}")

        test_texts_batch = [
            "Hello, world!",
            "How are you doing today?",
            "Cybersecurity is important."
        ]
        embeddings_batch = ollama_embedder.embed_texts(test_texts_batch)
        print(f"\nBatch embeddings (first 5 values of each):")
        for i, emb in enumerate(embeddings_batch):
            print(f"  Text {i+1}: {emb[:5]}...")
            print(f"  Dimension: {len(emb)}")

    except ConnectionError as e:
        print(f"Ollama connection error: {e}")
        print("Please ensure your Ollama server is running and accessible at the specified endpoint.")
        print(f"You might need to run `ollama run {OLLAMA_MODEL}` or `ollama serve`.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
