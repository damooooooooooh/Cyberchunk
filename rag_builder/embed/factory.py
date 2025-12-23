from typing import Dict, Any
from rag_builder.embed.embedder import Embedder
from rag_builder.embed.ollama_embedder import OllamaEmbedder
from rag_builder.embed.bedrock_embedder import BedrockEmbedder

def get_embedder(config: Dict[str, Any]) -> Embedder:
    """
    Factory function to get the appropriate Embedder instance based on configuration.
    """
    embed_config = config.get("embeddings", {})
    provider = embed_config.get("provider")

    if provider == "ollama":
        ollama_config = embed_config.get("ollama", {})
        endpoint = ollama_config.get("endpoint")
        model = ollama_config.get("model")
        if not all([endpoint, model]):
            raise ValueError("Ollama embedding configuration missing endpoint or model.")
        return OllamaEmbedder(endpoint=endpoint, model=model)
    elif provider == "bedrock":
        bedrock_config = embed_config.get("bedrock", {})
        region = bedrock_config.get("region")
        model = bedrock_config.get("model")
        aws_profile = bedrock_config.get("aws_profile")
        if not all([region, model]):
            raise ValueError("Bedrock embedding configuration missing region or model.")
        return BedrockEmbedder(region=region, model=model, aws_profile=aws_profile)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}")

if __name__ == '__main__':
    # Example usage with a mock config
    mock_ollama_config = {
        "embeddings": {
            "provider": "ollama",
            "ollama": {
                "endpoint": "http://localhost:11434",
                "model": "nomic-embed-text"
            }
        }
    }
    mock_bedrock_config = {
        "embeddings": {
            "provider": "bedrock",
            "bedrock": {
                "region": "us-east-1",
                "model": "amazon.titan-embed-text-v2:0",
                "aws_profile": "default"
            }
        }
    }

    try:
        ollama_embedder_instance = get_embedder(mock_ollama_config)
        print(f"Instantiated Ollama Embedder: {ollama_embedder_instance.model_name}")
        # Test it
        # emb = ollama_embedder_instance.embed_text("test")
        # print(f"Ollama test embedding len: {len(emb)}")
    except ValueError as e:
        print(f"Ollama config error: {e}")
    except Exception as e:
        print(f"Ollama embedder instantiation failed: {e}")


    try:
        bedrock_embedder_instance = get_embedder(mock_bedrock_config)
        print(f"Instantiated Bedrock Embedder: {bedrock_embedder_instance.model_name}")
        # Test it
        # emb = bedrock_embedder_instance.embed_text("test")
        # print(f"Bedrock test embedding len: {len(emb)}")
    except ValueError as e:
        print(f"Bedrock config error: {e}")
    except Exception as e:
        print(f"Bedrock embedder instantiation failed: {e}")

