"""OpenRouter LLM client for OP-05.

Uses poolside/laguna-xs-2.1:free as primary with automatic fallback to
high-throughput financial models (inclusionai/ling-3.0-flash-fin:free) on 429 rate limits.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_env(env_path: Optional[Path] = None) -> dict[str, str]:
    """Parse .env file into a dict without external libraries."""
    env = {}
    path = env_path or Path(__file__).resolve().parent.parent / ".env"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("\"'")
    return env


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        env = load_env()
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or env.get("OPENROUTER_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENROUTER_BASE_URL") or env.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")).rstrip("/")
        primary_model = model or os.environ.get("LLM_MODEL") or env.get("LLM_MODEL", "poolside/laguna-xs-2.1:free")
        self.models = [primary_model, "inclusionai/ling-3.0-flash-fin:free", "nvidia/nemotron-3.5-lightning:free"]
        # Deduplicate while preserving order
        self.models = list(dict.fromkeys(self.models))

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1500,
    ) -> str:
        """Call chat completions with model fallback on rate limit."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/Deployment-inc/Deployment.inc-Hiring-Problems",
            "X-Title": "Ask the Policy Book",
        }

        last_error = None
        for model in self.models:
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers)

            for attempt in range(2):
                try:
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        msg = data["choices"][0]["message"]
                        content = msg.get("content") or ""
                        if not content and "reasoning" in msg:
                            content = msg["reasoning"]
                        return content
                except urllib.error.HTTPError as e:
                    last_error = e
                    if e.code == 429:
                        time.sleep(1.5)
                        continue
                    break
                except Exception as e:
                    last_error = e
                    time.sleep(1)
                    continue

        raise RuntimeError(f"All LLM models exhausted. Last error: {last_error}")
