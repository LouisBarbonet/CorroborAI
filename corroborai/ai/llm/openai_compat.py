"""Fournisseurs LLM GRATUITS exposant une API compatible OpenAI (/chat/completions).

- Ollama   : local (http://localhost:11434), gratuit, aucune donnée ne quitte la machine.
- Groq     : clé gratuite (https://console.groq.com/keys), modèles Llama rapides.
- Gemini   : clé gratuite (https://aistudio.google.com/apikey), endpoint compatible OpenAI.
- OpenRouter : clé gratuite, modèles suffixés « :free ».
- Pollinations : sans clé, service public best-effort (API historique instable) — désactivé par défaut
  (ALLOW_KEYLESS_PUBLIC_LLM=1 pour l'activer).
"""
from __future__ import annotations

import json
import os

try:  # absent dans le navigateur (Pyodide) : le relais Cloudflare est alors utilisé
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

from .base import LLMError, Provider, parse_json


class OpenAICompatProvider(Provider):
    def __init__(self, name: str, base_url: str, model: str, key_env: str | None = None, local: bool = False,
                 enable_env: str | None = None, endpoint: str = "/chat/completions"):
        self.name, self.base_url, self.model = name, base_url.rstrip("/"), model
        self.endpoint = endpoint
        self.key_env, self.local, self.enable_env = key_env, local, enable_env
        self.timeout = float(os.environ.get("LLM_TIMEOUT", "90"))

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.key_env and os.environ.get(self.key_env):
            h["Authorization"] = f"Bearer {os.environ[self.key_env]}"
        if self.name == "openrouter":
            h["X-Title"] = "CorroborIA"
        return h

    def available(self) -> tuple[bool, str]:
        if self.enable_env and os.environ.get(self.enable_env, "0") != "1":
            return False, f"désactivé (définir {self.enable_env}=1)"
        if httpx is None:
            return False, "httpx indisponible (navigateur)"
        if self.key_env and not os.environ.get(self.key_env):
            return False, f"{self.key_env} non définie"
        if self.name == "ollama":
            try:
                r = httpx.get(self.base_url.replace("/v1", "") + "/api/tags", timeout=1.5)
                models = [m["name"] for m in r.json().get("models", [])]
            except (httpx.HTTPError, ValueError):
                return False, "serveur Ollama injoignable (localhost:11434)"
            if not models:
                return False, "aucun modèle Ollama installé (ollama pull qwen2.5:7b)"
            if self.model not in models and not any(m.startswith(self.model + ":") for m in models):
                self.model = models[0]
            return True, f"modèle local {self.model}"
        return True, "configuré"

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        sys_prompt = system + "\n\nRéponds UNIQUEMENT par un objet JSON valide conforme à ce schéma :\n" + json.dumps(schema, ensure_ascii=False)
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"}}
        url = f"{self.base_url}{self.endpoint}"
        try:
            r = httpx.post(url, json=body, headers=self._headers(), timeout=self.timeout)
            if r.status_code in (400, 422, 500):  # paramètres optionnels non supportés par certains modèles
                body.pop("response_format", None)
                body.pop("temperature", None)
                r = httpx.post(url, json=body, headers=self._headers(), timeout=self.timeout)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        except httpx.TimeoutException as e:
            raise LLMError(f"{self.name} : délai dépassé") from e
        except httpx.HTTPStatusError as e:
            raise LLMError(f"{self.name} : HTTP {e.response.status_code}") from e
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LLMError(f"{self.name} : {e}") from e
        return parse_json(content)


def free_providers() -> dict[str, OpenAICompatProvider]:
    return {
        "ollama": OpenAICompatProvider("ollama", os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
                                       os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"), local=True),
        "groq": OpenAICompatProvider("groq", "https://api.groq.com/openai/v1",
                                     os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"), key_env="GROQ_API_KEY"),
        "gemini": OpenAICompatProvider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
                                       os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), key_env="GEMINI_API_KEY"),
        "openrouter": OpenAICompatProvider("openrouter", "https://openrouter.ai/api/v1",
                                           os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
                                           key_env="OPENROUTER_API_KEY"),
        "pollinations": OpenAICompatProvider("pollinations", "https://text.pollinations.ai/openai",
                                             os.environ.get("POLLINATIONS_MODEL", "openai"), enable_env="ALLOW_KEYLESS_PUBLIC_LLM",
                                             endpoint=""),
    }
