"""Routeur « relais » : utilisé par le moteur exécuté dans le navigateur (Pyodide) sur GitHub Pages.

La clé Gemini n'est jamais côté navigateur : le moteur envoie uniquement des données structurées
(champ + cas ambigus, ou statistiques) au relais Cloudflare, qui construit lui-même la consigne.
- Les réponses déjà obtenues lors de la génération de l'instantané sont rejouées sans appel (clé = SHA-256
  du corps de requête canonique), ce qui rend le premier recalcul instantané et gratuit.
- En cas d'erreur du relais (quota, limite, réseau), repli automatique sur l'analyse locale (gabarit).
"""
from __future__ import annotations

import hashlib
import json
import sys

from .base import LLMError
from .router import BATCH, LLMRouter, _norm_verdict
from .template import TemplateProvider


def canonical_key(route: str, payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{route}\x1f{body}".encode("utf-8")).hexdigest()


def _post(url: str, payload: dict, timeout_s: int = 60) -> dict:
    data = json.dumps(payload, ensure_ascii=False)
    if sys.platform == "emscripten":  # navigateur : XHR synchrone autorisé dans un Web Worker
        from js import XMLHttpRequest  # type: ignore

        xhr = XMLHttpRequest.new()
        xhr.open("POST", url, False)
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send(data)
        status, text = int(xhr.status), str(xhr.responseText or "")
    else:  # hors navigateur (tests, scripts)
        import httpx

        r = httpx.post(url, content=data.encode("utf-8"), headers={"Content-Type": "application/json"}, timeout=timeout_s)
        status, text = r.status_code, r.text
    try:
        body = json.loads(text) if text else {}
    except json.JSONDecodeError:
        body = {}
    if status != 200:
        raise LLMError(body.get("erreur") or f"relais HTTP {status}")
    return body


class RelayRouter(LLMRouter):
    def __init__(self, url: str, recorded: dict | None = None, post=_post):
        self.url = url.rstrip("/")
        self.recorded = recorded or {}
        self.post = post
        self.trace: list[dict] = []
        self.cache_hits = 0
        self.model = "gemini"
        self._failed: str | None = None

    def status(self) -> dict:
        ok = bool(self.url) and not self._failed
        rows = [{"fournisseur": "relais", "modele": self.model, "disponible": ok, "local": False,
                 "detail": (f"relais Cloudflare {self.url}" if ok else (self._failed or "aucune URL de relais configurée"))},
                {"fournisseur": "gabarit-local", "modele": "", "disponible": True, "local": True,
                 "detail": "toujours disponible (aucun appel externe)"}]
        return {"actif": "relais" if ok else "gabarit-local", "fournisseurs": rows, "ordre": ["relais", "gabarit-local"]}

    def _request(self, route: str, payload: dict) -> tuple[dict, str]:
        key = canonical_key(route, payload)
        if key in self.recorded:
            self.cache_hits += 1
            rec = self.recorded[key]
            self.trace.append({"fournisseur": rec["fournisseur"], "statut": "réponse rejouée (instantané)"})
            return rec["reponse"], rec["fournisseur"]
        if not self.url or self._failed:
            raise LLMError(self._failed or "relais non configuré")
        try:
            body = self.post(f"{self.url}/{route}", payload)
        except LLMError as e:
            self._failed = str(e)
            self.trace.append({"fournisseur": "relais", "statut": f"échec → repli : {e}"})
            raise
        label = f"gemini/{body.get('modele', self.model)}"
        self.model = body.get("modele", self.model)
        if body.get("cached"):
            self.cache_hits += 1
        self.trace.append({"fournisseur": label, "statut": "cache du relais" if body.get("cached") else "ok"})
        return body, label

    def judge(self, champ: str, regle: str, cases: list[dict]) -> tuple[dict[str, dict], str]:
        results: dict[str, dict] = {}
        used = TemplateProvider.name
        for i in range(0, len(cases), BATCH):
            chunk = cases[i:i + BATCH]
            ids = {c["id"] for c in chunk}
            try:
                body, used = self._request("judge", {"champ": champ, "cas": chunk})
                clean = {}
                for c in body.get("cas", []):
                    v = _norm_verdict(c.get("verdict"))
                    if c.get("id") in ids and v:
                        clean[c["id"]] = {"verdict": v, "confiance": max(0.0, min(1.0, float(c.get("confiance", 0.5)))),
                                          "justification": str(c.get("justification", "")).strip()}
                if len(clean) < len(ids):
                    raise LLMError(f"réponse incomplète du relais ({len(clean)}/{len(ids)})")
                results.update(clean)
            except LLMError:
                results.update({c["id"]: c for c in TemplateProvider.judge(chunk)["cas"]})
                used = TemplateProvider.name
        return results, used

    def summarize(self, stats: dict) -> tuple[dict, str]:
        try:
            body, used = self._request("summary", stats)
            if not isinstance(body.get("resume"), str) or not isinstance(body.get("causes_racines"), list):
                raise LLMError("synthèse invalide")
            return {"resume": body["resume"], "causes_racines": body["causes_racines"]}, used
        except LLMError:
            return TemplateProvider.summarize(stats), TemplateProvider.name


class RecordingRouter:
    """Enveloppe un routeur et enregistre chaque échange au format du relais (pour l'instantané)."""

    def __init__(self, inner: LLMRouter):
        self.inner = inner
        self.recorded: dict[str, dict] = {}
        self.trace = inner.trace

    @property
    def cache_hits(self):
        return self.inner.cache_hits

    def status(self):
        return self.inner.status()

    def judge(self, champ, regle, cases):
        out = {}
        used = TemplateProvider.name
        for i in range(0, len(cases), BATCH):
            chunk = cases[i:i + BATCH]
            res, used = self.inner.judge(champ, regle, chunk)
            out.update(res)
            if not used.startswith("gabarit"):
                self.recorded[canonical_key("judge", {"champ": champ, "cas": chunk})] = {
                    "fournisseur": used, "reponse": {"cas": [{"id": k, **v} for k, v in res.items()]}}
        return out, used

    def summarize(self, stats):
        res, used = self.inner.summarize(stats)
        if not used.startswith("gabarit"):
            self.recorded[canonical_key("summary", stats)] = {"fournisseur": used, "reponse": res}
        return res, used
