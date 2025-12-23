import boto3
import json
from typing import List, Dict, Any, Optional
from rag_builder.llm.client import LLMClient

class BedrockLLMClient(LLMClient):
    """Concrete implementation of LLMClient for AWS Bedrock."""

    def __init__(self, region: str, model: str, aws_profile: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 1024):
        self._region = region
        self._model_name = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._bedrock_runtime = self._initialize_bedrock_client(aws_profile)
        print(f"Initialized BedrockLLMClient with region: {self._region}, model: {self._model_name}")

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

    def _prepare_body(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        if self._model_name.startswith("anthropic.claude"):
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": kwargs.get("max_tokens", self._max_tokens),
                "temperature": kwargs.get("temperature", self._temperature),
            }
        elif self._model_name.startswith("amazon.titan"):
            return {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": kwargs.get("max_tokens", self._max_tokens),
                    "temperature": kwargs.get("temperature", self._temperature),
                }
            }
        # Add other model families as needed (e.g., AI21, Cohere)
        else:
            raise ValueError(f"Unsupported Bedrock LLM model family for text generation: {self._model_name}")

    def _call_bedrock_invoke(self, prompt: str, **kwargs: Any) -> str:
        body = self._prepare_body(prompt, **kwargs)
        try:
            response = self._bedrock_runtime.invoke_model(
                body=json.dumps(body),
                modelId=self._model_name,
                accept="application/json",
                contentType="application/json"
            )
            response_body = json.loads(response.get("body").read())

            if self._model_name.startswith("anthropic.claude"):
                return response_body["content"][0]["text"]
            elif self._model_name.startswith("amazon.titan"):
                return response_body["results"][0]["outputText"]
            else:
                raise ValueError(f"Unexpected response format for model: {self._model_name}")
        except self._bedrock_runtime.exceptions.ValidationException as e:
            raise ValueError(f"Bedrock API validation error: {e}")
        except Exception as e:
            raise ConnectionError(f"Error calling Bedrock API for model {self._model_name}: {e}")

    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        return self._call_bedrock_invoke(prompt, **kwargs)

    def generate_json(self, prompt: str, schema: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        # For Bedrock, we often guide the LLM to produce JSON using prompt engineering.
        # Some models (like newer Claude versions) might have native JSON modes.
        # This implementation uses prompt engineering and then attempts to parse and validate.
        
        # Add a system prompt to guide JSON output if using Claude
        full_prompt = prompt
        if self._model_name.startswith("anthropic.claude"):
            full_prompt = f"{prompt}\n\n" \
                          f"The output must be a valid JSON object matching the following schema:\n" \
                          f"```json\n{json.dumps(schema, indent=2)}\n```\n" \
                          f"Do not include any other text or explanation."
            # Also set response_json property if model supports (e.g. Claude 3 Haiku)
            # This is model specific and might require changes in _prepare_body
        
        raw_output = self._call_bedrock_invoke(full_prompt, **kwargs)

        # Attempt to extract JSON from markdown code block if LLM wraps it
        if "```json" in raw_output:
            try:
                json_start = raw_output.find("```json") + len("```json")
                json_end = raw_output.find("```", json_start)
                raw_output = raw_output[json_start:json_end].strip()
            except ValueError:
                pass # If parsing fails, fall back to whole output

        try:
            generated_json = json.loads(raw_output)
            # Basic validation: check if top-level keys match schema properties if schema is simple
            # More robust validation would involve a dedicated JSON schema validator
            if schema and isinstance(generated_json, dict) and "properties" in schema:
                for key in generated_json:
                    if key not in schema["properties"]:
                        print(f"Warning: Generated JSON contains unexpected key '{key}'.")
            return generated_json
        except json.JSONDecodeError as e:
            raise ValueError(f"Bedrock LLM response was not valid JSON: '{raw_output}' - {e}")

if __name__ == '__main__':
    # Example usage - replace with your actual AWS region, model, and profile
    from dotenv import load_dotenv
    import os

    load_dotenv() # Load AWS credentials from .env if available

    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_LLM_MODEL = os.getenv("BEDROCK_LLM_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0") # Or 'amazon.titan-text-express-v1'
    AWS_PROFILE = os.getenv("AWS_PROFILE", None) # e.g., 'default' or a specific profile

    if AWS_PROFILE:
        print(f"Using AWS profile: {AWS_PROFILE}")
    else:
        print("Using default AWS credentials chain (environment variables, ~/.aws/credentials, etc.)")

    try:
        bedrock_llm_client = BedrockLLMClient(region=AWS_REGION, model=BEDROCK_LLM_MODEL, aws_profile=AWS_PROFILE, temperature=0.2)
        
        # Test generate_text
        text_prompt = "Explain why large language models are useful for cybersecurity analysis in one paragraph."
        print(f"\n--- Testing generate_text with {bedrock_llm_client.model_name} ---")
        explanation = bedrock_llm_client.generate_text(text_prompt, max_tokens=200)
        print("Generated explanation:\n", explanation)

        # Test generate_json
        json_prompt = "From the following text, extract the person's name and their role: 'Dr. Evelyn Reed, a leading AI researcher, presented her findings.'"
        json_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string"}
            },
            "required": ["name", "role"]
        }
        print(f"\n--- Testing generate_json with {bedrock_llm_client.model_name} ---")
        extracted_json = bedrock_llm_client.generate_json(json_prompt, json_schema, temperature=0.1)
        print("Extracted JSON:\n", json.dumps(extracted_json, indent=2))
        assert extracted_json.get("name") == "Dr. Evelyn Reed"
        assert extracted_json.get("role") == "AI researcher"
        print("JSON extraction test passed.")

    except ConnectionError as e:
        print(f"Bedrock connection error: {e}")
        print("Please ensure your AWS credentials are configured correctly and you have access to Bedrock in the specified region.")
        print("You might also need to enable the specific model via the Bedrock console.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
