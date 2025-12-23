import boto3
import json
from typing import List, Dict, Any, Optional
from rag_builder.embed.embedder import Embedder

class BedrockEmbedder(Embedder):
    """Concrete implementation of Embedder for AWS Bedrock."""

    def __init__(self, region: str, model: str, aws_profile: Optional[str] = None):
        self._region = region
        self._model_name = model
        self._bedrock_runtime = self._initialize_bedrock_client(aws_profile)
        print(f"Initialized BedrockEmbedder with region: {self._region}, model: {self._model_name}")

    def _initialize_bedrock_client(self, aws_profile: Optional[str]):
        try:
            if aws_profile:
                session = boto3.Session(profile_name=aws_profile, region_name=self._region)
            else:
                session = boto3.Session(region_name=self._region)
            
            return session.client(service_name="bedrock-runtime", region_name=self._region)
        except Exception as e:
            raise ConnectionError(f"Failed to initialize AWS Bedrock client: {e}")

    @property
    def model_name(self) -> str:
        return self._model_name

    def _call_bedrock_api(self, text: str) -> List[float]:
        body = {
            "inputText": text
        }
        try:
            response = self._bedrock_runtime.invoke_model(
                body=json.dumps(body),
                modelId=self._model_name,
                accept="application/json",
                contentType="application/json"
            )
            response_body = json.loads(response.get("body").read())
            if "embedding" in response_body:
                return response_body["embedding"]
            else:
                raise ValueError(f"Bedrock API response missing 'embedding' field: {response_body}")
        except self._bedrock_runtime.exceptions.ValidationException as e:
            raise ValueError(f"Bedrock API validation error: {e}")
        except Exception as e:
            raise ConnectionError(f"Error calling Bedrock API for model {self._model_name}: {e}")

    def embed_text(self, text: str) -> List[float]:
        # Bedrock's Titan Embed models typically take a single input for embedding.
        # Check specific model documentation if batching is directly supported via body.
        return self._call_bedrock_api(text)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # For batch embedding with Bedrock's current Titan models, we typically
        # call the API for each text. Some models might support batching in a single call.
        # This implementation assumes single calls.
        embeddings = []
        for text in texts:
            embeddings.append(self.embed_text(text))
        return embeddings

if __name__ == '__main__':
    # Example usage - replace with your actual AWS region, model, and profile
    import json
    from dotenv import load_dotenv
    import os

    load_dotenv() # Load AWS credentials from .env if available

    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_MODEL = os.getenv("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
    AWS_PROFILE = os.getenv("AWS_PROFILE", None) # e.g., 'default' or a specific profile

    if AWS_PROFILE:
        print(f"Using AWS profile: {AWS_PROFILE}")
    else:
        print("Using default AWS credentials chain (environment variables, ~/.aws/credentials, etc.)")

    try:
        bedrock_embedder = BedrockEmbedder(region=AWS_REGION, model=BEDROCK_MODEL, aws_profile=AWS_PROFILE)
        
        test_text_single = "This is a test sentence for Bedrock embedding."
        embedding_single = bedrock_embedder.embed_text(test_text_single)
        print(f"Single embedding (first 5 values): {embedding_single[:5]}...")
        print(f"Embedding dimension: {len(embedding_single)}")

        test_texts_batch = [
            "Hello, Bedrock!",
            "AWS Bedrock is a managed service.",
            "AI and ML are transforming cybersecurity."
        ]
        embeddings_batch = bedrock_embedder.embed_texts(test_texts_batch)
        print(f"\nBatch embeddings (first 5 values of each):")
        for i, emb in enumerate(embeddings_batch):
            print(f"  Text {i+1}: {emb[:5]}...")
            print(f"  Dimension: {len(emb)}")

    except ConnectionError as e:
        print(f"Bedrock connection error: {e}")
        print("Please ensure your AWS credentials are configured correctly and you have access to Bedrock in the specified region.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
