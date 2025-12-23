from typing import Dict, Any
from rag_builder.llm.client import LLMClient
from rag_builder.llm.ollama_llm_client import OllamaLLMClient
from rag_builder.llm.bedrock_llm_client import BedrockLLMClient
from rag_builder.llm.openai_llm_client import OpenAILLMClient

def get_llm_client(config: Dict[str, Any]) -> LLMClient:
    """
    Factory function to get the appropriate LLMClient instance based on configuration.
    Expects 'llm_validation' section in config.
    """
    llm_config = config.get("llm_validation", {})
    provider = llm_config.get("provider")
    
    # Common parameters for LLM clients
    temperature = llm_config.get("temperature", 0.1)
    max_tokens = llm_config.get("max_tokens", 1024)

    if provider == "ollama":
        ollama_settings = llm_config.get("ollama", {})
        endpoint = ollama_settings.get("endpoint")
        model = ollama_settings.get("model")
        if not all([endpoint, model]):
            raise ValueError("Ollama LLM configuration missing endpoint or model.")
        return OllamaLLMClient(endpoint=endpoint, model=model, temperature=temperature, max_tokens=max_tokens)
    elif provider == "bedrock":
        bedrock_settings = llm_config.get("bedrock", {})
        region = bedrock_settings.get("region")
        model = bedrock_settings.get("model")
        aws_profile = bedrock_settings.get("aws_profile")
        if not all([region, model]):
            raise ValueError("Bedrock LLM configuration missing region or model.")
        return BedrockLLMClient(region=region, model=model, aws_profile=aws_profile, temperature=temperature, max_tokens=max_tokens)
    elif provider == "openai":
        openai_settings = llm_config.get("openai", {})
        model = openai_settings.get("model")
        api_key = openai_settings.get("api_key")  # optional, falls back to env OPENAI_API_KEY
        base_url = openai_settings.get("base_url")  # optional, for proxies/azure
        if not model:
            raise ValueError("OpenAI LLM configuration missing model.")
        return OpenAILLMClient(model=model, api_key=api_key, base_url=base_url, temperature=temperature, max_tokens=max_tokens)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

if __name__ == '__main__':
    # Example usage with a mock config
    mock_ollama_config = {
        "llm_validation": {
            "enabled": True,
            "provider": "ollama",
            "ollama": {
                "endpoint": "http://localhost:11434",
                "model": "llama3"
            },
            "temperature": 0.2,
            "max_tokens": 500
        }
    }
    mock_bedrock_config = {
        "llm_validation": {
            "enabled": True,
            "provider": "bedrock",
            "bedrock": {
                "region": "us-east-1",
                "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                "aws_profile": "default"
            },
            "temperature": 0.1,
            "max_tokens": 1000
        }
    }

    try:
        ollama_llm_client_instance = get_llm_client(mock_ollama_config)
        print(f"Instantiated Ollama LLM Client: {ollama_llm_client_instance.model_name}")
    except ValueError as e:
        print(f"Ollama config error: {e}")
    except Exception as e:
        print(f"Ollama LLM client instantiation failed: {e}")


    try:
        bedrock_llm_client_instance = get_llm_client(mock_bedrock_config)
        print(f"Instantiated Bedrock LLM Client: {bedrock_llm_client_instance.model_name}")
    except ValueError as e:
        print(f"Bedrock config error: {e}")
    except Exception as e:
        print(f"Bedrock LLM client instantiation failed: {e}")
