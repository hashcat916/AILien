"""Cloud LLM client (OpenAI-compatible) with tool/function calling and vision support.

Works with xAI, Groq, OpenAI, Together, or any OpenAI-compatible API provider.
Uses the standard /chat/completions endpoint via requests.
"""
import json
import logging
from typing import Any

import requests

import config
from utils.helpers import print_error

logger = logging.getLogger("agent")


class CloudLLMClient:
    """Client for cloud LLM APIs (OpenAI-compatible) with tool calling and vision."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or config.CLOUD_API_KEY
        self.model = model or config.CLOUD_MODEL
        # Ensure base_url ends at /v1 (no trailing slash)
        raw = (base_url or config.CLOUD_BASE_URL).rstrip("/")
        self.base_url = raw
        self.chat_url = f"{raw}/chat/completions"

        if not self.api_key:
            logger.warning(
                "CLOUD_API_KEY not set. Set it via environment variable, .env file, or config.py.\n"
                "  xAI: https://console.x.ai/\n"
                "  Groq: https://console.groq.com/keys"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send a chat request to the cloud API.
        Returns a response message dict compatible with the Ollama format.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": config.CLOUD_TEMPERATURE,
            "max_tokens": config.CLOUD_MAX_TOKENS,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            resp = requests.post(
                self.chat_url,
                headers=self._headers(),
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]

            result: dict[str, Any] = {
                "role": msg.get("role", "assistant"),
                "content": msg.get("content") or "",
            }
            if msg.get("tool_calls"):
                result["tool_calls"] = [
                    {
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in msg["tool_calls"]
                ]
            return result
        except requests.HTTPError as exc:
            try:
                err = exc.response.json() if exc.response else {}
                detail = err.get("error", err.get("message", str(exc)))
            except Exception:
                detail = str(exc)
            logger.exception("Cloud API chat failed")
            print_error(f"Cloud API error: {detail}")
            return {"role": "assistant", "content": f"Error: {detail}"}
        except Exception as exc:
            logger.exception("Cloud API chat failed")
            print_error(f"Cloud API request failed: {exc}")
            return {"role": "assistant", "content": f"Error: {exc}"}

    def analyze_image(self, image_b64: str, prompt: str | None = None) -> str:
        """
        Send an image to a vision-capable model and return its text description.
        If the provider does not support vision, gracefully degrades.
        """
        vision_prompt = prompt or config.VISION_PROMPT
        vision_model = config.VISION_MODEL or self.model
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ]
            resp = requests.post(
                self.chat_url,
                headers=self._headers(),
                json={
                    "model": vision_model,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.2,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"].get("content", "")
        except requests.HTTPError as exc:
            try:
                body = exc.response.json() if exc.response else {}
            except Exception:
                body = exc.response.text if exc.response else ""
            status = exc.response.status_code if exc.response else "unknown"
            logger.warning(f"Vision analysis failed ({status}): {body}")
            return f"[Vision unavailable: {body or exc}. Check your API key and vision model availability.]"
        except Exception as exc:
            logger.warning(f"Vision analysis failed: {exc}")
            return f"[Vision unavailable: {exc}. Check your API key and vision model availability.]"


# Module-level cloud client for use by tools
_CLOUD_CLIENT: CloudLLMClient | None = None


def get_cloud_client() -> CloudLLMClient:
    """Lazy-load the shared cloud LLM client."""
    global _CLOUD_CLIENT
    if _CLOUD_CLIENT is None:
        _CLOUD_CLIENT = CloudLLMClient()
    return _CLOUD_CLIENT
