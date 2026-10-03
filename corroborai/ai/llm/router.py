"""Routeur LLM avec repli automatique (failsafe).

Ordre par défaut : claude → ollama → groq → gemini → openrouter → pollinations → gabarit-local.
Chaque fournisseur indisponible ou en erreur (timeout, quota, JSON invalide) est sauté ; le gabarit
local garantit que le pipeline aboutit toujours, gratuitement et sans appel externe.

Confidentialité : seuls des extraits minimaux et anonymisés (valeurs du champ concerné et signaux
de l'analyse locale) sont transmis — jamais les fichiers complets.
"""
from __future__ import annotations

import json
import os

from ...models import ANOMALIE, JUSTIFIE
from .base import DiskCache, LLMError, Provider, load_dotenv, load_prompts
from .claude import ClaudeProvider
from .openai_compat import free_providers
from .template import TemplateProvider

DEFAULT_ORDER = "claude,ollama,groq,gemini,openrouter,pollinations,template"

PROMPTS = load_prompts()
SYSTEM_JUDGE = PROMPTS["judge_system"]
SYSTEM_SUMMARY = PROMPTS["summary_system"]
SYSTEM_CHAT = PROMPTS["chat_system"]
JUDGE_SCHEMA = PROMPTS["judge_schema"]
SUMMARY_SCHEMA = PROMPTS["summary_schema"]
CHAT_SCHEMA = PROMPTS["chat_schema"]

BATCH = 25  # = taille maximale acceptée par le relais Cloudflare


def _norm_verdict(v: str) -> str | None:
    s = (v or "").lower()
    if "anomal" in s or "erreur" in s:
        return ANOMALIE
    if "justif" in s or "ecart" in s or "écart" in s:
        return JUSTIFIE
    return None


class LLMRouter:
    def __init__(self, order: str | None = None):
        load_dotenv()
        names = [n.strip() for n in (order or os.environ.get("LLM_PROVIDERS", DEFAULT_ORDER)).split(",") if n.strip()]
        free = free_providers()
        registry: dict[str, Provider] = {"claude": ClaudeProvider(), "template": TemplateProvider(), **free}
        self.providers: list[Provider] = [registry[n] for n in names if n in registry]
        if not any(isinstance(p, TemplateProvider) for p in self.providers):
            self.providers.append(TemplateProvider())
        self.cache = DiskCache()
        self.trace: list[dict] = []
        self.cache_hits = 0
        self._avail: dict[str, tuple[bool, str]] = {}

    def _available(self, p: Provider) -> tuple[bool, str]:
        if p.name not in self._avail:
            self._avail[p.name] = p.available()
        return self._avail[p.name]

    def status(self) -> dict:
        rows = []
        for p in self.providers:
            ok, why = self._available(p)
            rows.append({"fournisseur": p.name, "modele": p.model, "disponible": ok, "detail": why, "local": p.local})
        active = next((r["fournisseur"] for r in rows if r["disponible"]), "gabarit-local")
        return {"actif": active, "fournisseurs": rows, "ordre": [p.name for p in self.providers]}

    def _call(self, system: str, user: str, schema: dict, validate) -> tuple[dict, str]:
        out, label, _ = self._call_ex(system, user, schema, validate)
        return out, label

    def _call_ex(self, system: str, user: str, schema: dict, validate) -> tuple[dict, str, bool]:
        """Comme _call, mais indique aussi si la réponse provient du cache disque."""
        for p in self.providers:
            if isinstance(p, TemplateProvider):
                break
            ok, why = self._available(p)
            if not ok:
                continue
            key = DiskCache.key(p.label, system, user, json.dumps(schema, sort_keys=True))
            cached = self.cache.get(key)
            if cached is not None:
                self.trace.append({"fournisseur": p.label, "statut": "réponse rejouée depuis le cache"})
                self.cache_hits += 1
                return cached, p.label, True
            try:
                out = validate(p.complete_json(system, user, schema))
                self.cache.set(key, out)
                self.trace.append({"fournisseur": p.label, "statut": "ok"})
                return out, p.label, False
            except (LLMError, ValueError, KeyError, TypeError) as e:
                self.trace.append({"fournisseur": p.label, "statut": f"échec → repli : {e}"})
                self._avail[p.name] = (False, f"échec à l'exécution : {e}")
        raise LLMError("aucun fournisseur LLM disponible")

    def judge(self, champ: str, regle: str, cases: list[dict]) -> tuple[dict[str, dict], str]:
        """Arbitre un lot de cas ambigus d'un même champ. Retourne ({id: décision}, fournisseur)."""
        results: dict[str, dict] = {}
        used = TemplateProvider.name
        for i in range(0, len(cases), BATCH):
            chunk = cases[i:i + BATCH]
            ids = {c["id"] for c in chunk}
            user = json.dumps({"champ": champ, "regle_mapping": regle, "cas": chunk}, ensure_ascii=False, indent=1)

            def validate(out: dict) -> dict:
                clean = {}
                for c in out.get("cas", []):
                    v = _norm_verdict(c.get("verdict"))
                    if c.get("id") in ids and v:
                        clean[c["id"]] = {"verdict": v, "confiance": max(0.0, min(1.0, float(c.get("confiance", 0.5)))),
                                          "justification": str(c.get("justification", "")).strip()}
                if len(clean) < len(ids):
                    raise ValueError(f"réponse incomplète ({len(clean)}/{len(ids)} cas)")
                return {"cas": clean}

            try:
                out, used = self._call(SYSTEM_JUDGE, user, JUDGE_SCHEMA, validate)
                results.update(out["cas"])
            except LLMError:
                tpl = TemplateProvider.judge(chunk)
                results.update({c["id"]: c for c in tpl["cas"]})
                used = TemplateProvider.name
        return results, used

    def summarize(self, stats: dict) -> tuple[dict, str]:
        def validate(out: dict) -> dict:
            if not isinstance(out.get("resume"), str) or not isinstance(out.get("causes_racines"), list):
                raise ValueError("synthèse invalide")
            return out

        try:
            return self._call(SYSTEM_SUMMARY, json.dumps(stats, ensure_ascii=False, indent=1), SUMMARY_SCHEMA, validate)
        except LLMError:
            return TemplateProvider.summarize(stats), TemplateProvider.name

    def chat(self, messages: list[dict], context: str) -> dict:
        """Assistant du jury : répond à partir du contexte du projet uniquement (même consigne que le relais)."""
        system = SYSTEM_CHAT.replace("{{context}}", context)
        convo = "\n\n".join(f"{'Question' if m['role'] == 'user' else 'Réponse précédente'} : {m['content']}" for m in messages)

        def validate(out: dict) -> dict:
            if not isinstance(out.get("reponse"), str) or not out["reponse"].strip():
                raise ValueError("réponse vide")
            return {"reponse": out["reponse"].strip()}

        try:
            out, provider, cached = self._call_ex(system, convo, CHAT_SCHEMA, validate)
            return {"reponse": out["reponse"], "fournisseur": provider, "cached": cached}
        except LLMError as e:
            raise LLMError("Aucun LLM disponible pour le chat (configurer une clé, voir .env.example).") from e
