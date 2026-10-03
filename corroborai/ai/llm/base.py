"""Contrat commun des fournisseurs LLM + utilitaires (parsing JSON robuste, cache disque, .env)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE_PATH = ROOT / "output" / ".llm_cache.json"
_lock = threading.Lock()


class LLMError(Exception):
    pass


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
    """Cache des réponses LLM (clé = fournisseur + modèle + prompt) : reproductibilité et économie d'appels."""

    def __init__(self, path: Path = CACHE_PATH):
        self.path = path
        try:
            self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (json.JSONDecodeError, OSError):
            self.data = {}

    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    def get(self, k: str):
        return self.data.get(k)

    def set(self, k: str, v) -> None:
        with _lock:
            self.data[k] = v
            if os.environ.get("LLM_CACHE", "1") == "0":
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
