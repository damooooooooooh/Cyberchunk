import json
import os
import re
from typing import Dict, Any, Optional

from openai import OpenAI

from rag_builder.llm.client import LLMClient


_ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _resolve_env_placeholder(value: Optional[str]) -> Optional[str]:
    """
    Allows config values like '${OPENAI_API_KEY}' to be resolved from the environment.
    If 'value' is a normal string (e.g., 'sk-...'), it's returned as-is.
    If it's exactly '${VARNAME}', returns os.getenv('VARNAME') (or None if unset).
    """
    if not value:
        return None
    v = value.strip()
    m = _ENV_PATTERN.match(v)
    if not m:
        return v
    env_name = m.group(1)
    return os.getenv(env_name)


class OpenAILLMClient(LLMClient):
    """
    OpenAI chat-based LLM client.
    Expects OPENAI_API_KEY in the environment or provided via api_key.
    Supports '${OPENAI_API_KEY}' style placeholders in config.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        base_url: Optional[str] = None
    ):
        # Resolve ${ENV_VAR} placeholders if present
        resolved_key = _resolve_env_placeholder(api_key)

        # If config attempted env-substitution but the env var is missing, fail clearly
        if api_key and api_key.strip().startswith("${") and api_key.strip().endswith("}") and not resolved_key:
            env_name = api_key.strip()[2:-1]
            raise ValueError(
                f"OpenAI api_key was set to '{api_key}' but environment variable '{env_name}' is not set."
            )

        client_kwargs: Dict[str, Any] = {}
        if resolved_key:
            client_kwargs["api_key"] = resolved_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(**client_kwargs)
        self._model_name = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        resp = self._client.chat.completions.create(
            model=self._model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
        )
        return resp.choices[0].message.content

    def generate_json(self, prompt: str, schema: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Requests JSON-formatted output and parses it. Uses OpenAI's JSON mode when available.
        """
        try:
            resp = self._client.chat.completions.create(
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", self._temperature),
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            return json.loads(content)
        except Exception:
            # Fallback: try to extract JSON object manually
            text = self.generate_text(prompt, **kwargs)
            text = text.replace("```json", "").replace("```", "").strip()
            match = re.search(r'(\{.*\})|(\[.*\])', text, re.DOTALL)
            if not match:
                raise ValueError("OpenAI response did not contain JSON.")
            return json.loads(match.group(0))
