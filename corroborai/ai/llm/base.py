"""Contrat commun des fournisseurs LLM + utilitaires (parsing JSON robuste, cache disque, .env)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / ".cache" / "llm"
PROMPTS_PATH = ROOT / "prompts" / "prompts.json"
_lock = threading.Lock()


class LLMError(Exception):
    pass


def load_prompts(path: Path = PROMPTS_PATH) -> dict:
    """Consignes partagées avec le relais Cloudflare (source unique : prompts/prompts.json)."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Chargeur .env minimal (n'écrase pas les variables déjà définies)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def parse_json(text: str) -> dict:
    """Extrait le premier objet JSON d'une réponse (tolère ```json …``` et texte parasite)."""
    if not text:
        raise LLMError("réponse vide")
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start = t.find("{")
        depth = 0
        for i in range(start, len(t)) if start >= 0 else []:
            depth += {"{": 1, "}": -1}.get(t[i], 0)
            if depth == 0:
                return json.loads(t[start:i + 1])
    raise LLMError("JSON introuvable dans la réponse")


class Provider:
    name = "base"
    model = ""
    local = False  # True : aucune donnée ne quitte la machine

    def available(self) -> tuple[bool, str]:
        raise NotImplementedError

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        raise NotImplementedError

    @property
    def label(self) -> str:
        return f"{self.name}/{self.model}" if self.model else self.name


class DiskCache:
    """Cache disque des réponses LLM (.cache/llm/<sha256>.json) : reproductibilité, aucune requête payée deux fois.
    Vidage : npm run cache:clear (ou supprimer le dossier)."""

    def __init__(self, directory: Path = CACHE_DIR):
        self.dir = directory

    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    def get(self, k: str):
        p = self.dir / f"{k}.json"
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, k: str, v) -> None:
        if os.environ.get("LLM_CACHE", "1") == "0":
            return
        with _lock:
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                (self.dir / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
