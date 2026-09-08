"""OpenRouter LLM client for OP-05 with multi-key rotation.

Cycles through a pool of OpenRouter API keys to balance quota usage across requests
and automatically fails over to the next key upon 429 or rate-limit errors.
Primary model: cohere/north-mini-code:free (fast, clean instruct, compliant JSON).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_env(env_path: Optional[Path] = None) -> dict[str, str]:
    """Parse .env file into a dict without external libraries."""
    env: dict[str, str] = {}
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
        api_keys: Optional[List[str]] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        env = load_env()
        raw_keys = (
            (api_keys and ",".join(api_keys))
            or os.environ.get("OPENROUTER_API_KEYS")
            or env.get("OPENROUTER_API_KEYS")
            or os.environ.get("OPENROUTER_API_KEY")
            or env.get("OPENROUTER_API_KEY", "")
        )
        self.keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        if not self.keys:
            self.keys = [""]
        self.current_key_idx = 0

        self.base_url = (
            base_url
            or os.environ.get("OPENROUTER_BASE_URL")
            or env.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        ).rstrip("/")

        primary_model = (
            model
            or os.environ.get("LLM_MODEL")
            or env.get("LLM_MODEL", "cohere/north-mini-code:free")
        )
        self.models = [
            primary_model,
            "cohere/north-mini-code:free",
            "inclusionai/ling-3.0-flash-fin:free",
            "nvidia/nemotron-3.5-lightning:free",
        ]
        # De-duplicate while preserving priority order
        self.models = list(dict.fromkeys(self.models))

    def _get_next_key(self) -> str:
        """Round-robin cycle to the next key."""
        key = self.keys[self.current_key_idx % len(self.keys)]
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        return key

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 400,
        max_retries_per_model: int = 2,
    ) -> str:
        """Call OpenRouter chat completions with key rotation and fast fallback."""
        last_error = None

        for model in self.models:
            for attempt in range(max_retries_per_model):
                # Acquire current key for this attempt
                api_key = self._get_next_key()
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/Deployment-inc/Deployment.inc-Hiring-Problems",
                    "X-Title": "Ask the Policy Book",
                }

                url = f"{self.base_url}/chat/completions"
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers=headers)

                try:
                    key_tag = api_key[-8:] if len(api_key) >= 8 else "none"
                    # print(f"[LLM] Model: {model} (key: ...{key_tag})...")
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        choice = data["choices"][0]
                        msg = choice["message"]
                        content = msg.get("content")

                        if content and content.strip():
                            return content.strip()

                        # Fallback for models outputting to reasoning
                        reasoning = msg.get("reasoning") or ""
                        if reasoning:
                            m_json = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", reasoning, re.DOTALL)
                            if m_json:
                                return m_json.group(1)
                            m_json2 = re.search(r"(\{.*\})", reasoning, re.DOTALL)
                            if m_json2:
                                return m_json2.group(1)

                        continue
                except urllib.error.HTTPError as e:
                    last_error = e
                    err_body = ""
                    try:
                        err_body = e.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass

                    key_tag = api_key[-8:] if len(api_key) >= 8 else "none"
                    print(f"[LLM Warning] {model} (key ...{key_tag}) HTTP {e.code}: {err_body[:90]}")
                    if e.code == 429:
                        # Immediately failover to next key in pool
                        time.sleep(0.5)
                        continue
                    break
                except Exception as e:
                    last_error = e
                    print(f"[LLM Warning] {model} EXCEPTION: {e}")
                    time.sleep(0.5)
                    continue

        raise RuntimeError(f"All LLM models and keys exhausted. Last error: {last_error}")
