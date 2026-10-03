"""Fournisseur Claude (Anthropic) — utilisé en priorité lorsqu'une clé ANTHROPIC_API_KEY est configurée."""
from __future__ import annotations

import json
import os

from .base import LLMError, Provider


class ClaudeProvider(Provider):
    name = "claude"

    def __init__(self):
        self.model = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
        self.timeout = float(os.environ.get("LLM_TIMEOUT", "90"))

    def available(self) -> tuple[bool, str]:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False, "ANTHROPIC_API_KEY non définie"
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, "paquet « anthropic » non installé"
        return True, "clé API configurée"

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        import anthropic

        client = anthropic.Anthropic(timeout=self.timeout, max_retries=1)
        params = dict(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        )
        try:
            # Repli serveur automatique si le modèle décline la requête (refus de sécurité).
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
        except anthropic.BadRequestError:
            resp = client.messages.create(**params)
        except anthropic.APIConnectionError as e:
            raise LLMError(f"connexion Claude impossible : {e}") from e
        except anthropic.RateLimitError as e:
            raise LLMError("limite de débit Claude atteinte") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"erreur Claude {e.status_code}") from e
        if resp.stop_reason == "refusal":
            raise LLMError("requête refusée par le modèle")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError("JSON invalide renvoyé par Claude") from e
