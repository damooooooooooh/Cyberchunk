import requests
import json
import re
from typing import List, Dict, Any, Optional
from rag_builder.llm.client import LLMClient

class OllamaLLMClient(LLMClient):
    """Concrete implementation of LLMClient for Ollama."""

    def __init__(self, endpoint: str, model: str, temperature: float = 0.7, max_tokens: int = 1024):
        self._endpoint = f"{endpoint.rstrip('/')}/api/generate"
        self._model_name = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        print(f"Initialized OllamaLLMClient with endpoint: {self._endpoint} and model: {self._model_name}")

    @property
    def model_name(self) -> str:
        return self._model_name

    def _call_ollama_generate(self, prompt: str, format_json: bool = False, **kwargs: Any) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}

        # If we're expecting a single JSON response, disable Ollama streaming
        stream_ollama = not format_json

        payload: Dict[str, Any] = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": stream_ollama,
            "options": {
                "temperature": kwargs.get("temperature", self._temperature),
                "num_predict": kwargs.get("max_tokens", self._max_tokens),
            },
        }
        if format_json:
            payload["format"] = "json"

        try:
            # IMPORTANT: only HTTP-stream when Ollama is streaming (stream=true)
            with requests.post(
                self._endpoint,
                headers=headers,
                json=payload,
                timeout=120,
                stream=stream_ollama,
            ) as response:
                response.raise_for_status()

                # Non-streaming: Ollama returns one JSON object
                if not stream_ollama:
                    data = response.json()
                    # Normalize return shape so callers can always read ["response"]
                    if "response" in data:
                        return {"response": data["response"]}
                    # Fallback: return entire body if it doesn't match expected envelope
                    return data

                # Streaming: Ollama returns NDJSON lines
                full_response = ""
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    obj = json.loads(line)
                    full_response += obj.get("response", "")
                    if obj.get("done"):
                        break

                if not full_response.strip():
                    raise ValueError("Ollama stream resulted in an empty response.")

                return {"response": full_response}

        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Ollama API request timed out after 120 seconds for model {self._model_name}"
            )
        except requests.exceptions.RequestException as e:
            error_message = f"Error connecting to Ollama API at {self._endpoint}. "
            if getattr(e, "response", None) is not None:
                error_message += f"Status Code: {e.response.status_code}. Response: {e.response.text}"
            else:
                error_message += str(e)
            raise ConnectionError(error_message)
        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to parse Ollama API response: {e}")


    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        result = self._call_ollama_generate(prompt, format_json=False, **kwargs)
        if "response" in result:
            return result["response"]
        else:
            raise ValueError(f"Ollama API response missing 'response' field: {result}")

    def generate_json(self, prompt: str, schema: Dict[str, Any], retries: int = 3, **kwargs: Any) -> Dict[str, Any]:
        # Ollama's `format: "json"` ensures a JSON response, but it doesn't validate against a schema.
        # This function adds more robust parsing and retries.
        for attempt in range(retries):
            try:
                result = self._call_ollama_generate(prompt, format_json=True, **kwargs)
                
                if "response" not in result or not result["response"].strip():
                    raise ValueError("Ollama response is empty.")

                response_text = result["response"]
                print(f"--- Raw LLM JSON Response (Attempt {attempt + 1}) ---")
                print(response_text)
                print("--- End Raw LLM JSON Response ---")
                
                # Use regex to find a JSON object, specifically looking for `{...}` or `[...]`
                # This is more robust than simple find() as it can ignore leading/trailing text.
                json_match = re.search(r'(\{.*\})|(\[.*\])', response_text, re.DOTALL)
                
                if not json_match:
                    raise ValueError(f"Could not find a valid JSON object in the response: {response_text}")

                json_string = json_match.group(0) # Get the matched JSON string

                json_response = json.loads(json_string)
                return json_response

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Attempt {attempt + 1}/{retries} failed: {e}")
                print(f"Problematic JSON string: {json_string if 'json_string' in locals() else 'N/A'}")
                if attempt + 1 == retries:
                    raise ValueError(f"Ollama response was not valid JSON after {retries} attempts: {result.get('response', '')}") from e
        
        raise ValueError("Should not be reached.")

if __name__ == '__main__':
    # Example usage - replace with your actual Ollama endpoint and model
    # Ensure Ollama server is running and model is available: ollama run llama3
    OLLAMA_ENDPOINT = "http://localhost:11434" # Default for local Ollama
    OLLAMA_MODEL = "llama3" # Or any other text generation model

    try:
        ollama_llm_client = OllamaLLMClient(endpoint=OLLAMA_ENDPOINT, model=OLLAMA_MODEL, temperature=0.2)
        
        # Test generate_text
        text_prompt = "Tell me a short story about a cybersecurity hero named Gemini."
        print(f"\n--- Testing generate_text with {ollama_llm_client.model_name} ---")
        story = ollama_llm_client.generate_text(text_prompt, max_tokens=150)
        print("Generated story:\n", story)

        # Test generate_json
        json_prompt = "Extract the name and job from the following text: 'My name is Alice and I am a software engineer.' Output as JSON with keys 'name' and 'job'."
        json_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "job": {"type": "string"}
            },
            "required": ["name", "job"]
        }
        print(f"\n--- Testing generate_json with {ollama_llm_client.model_name} ---")
        extracted_json = ollama_llm_client.generate_json(json_prompt, json_schema)
        print("Extracted JSON:\n", json.dumps(extracted_json, indent=2))
        assert extracted_json.get("name") == "Alice"
        assert extracted_json.get("job") == "software engineer"
        print("JSON extraction test passed.")

    except ConnectionError as e:
        print(f"Ollama connection error: {e}")
        print("Please ensure your Ollama server is running and accessible at the specified endpoint.")
        print(f"You might need to run `ollama run {OLLAMA_MODEL}` or `ollama serve`.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
