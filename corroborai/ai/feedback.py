"""Boucle de rétroaction expert.

Un expert fonctionnel peut corriger un verdict :
- portée « cas »   : la correction s'applique à ce constat précis (même identifiant) ;
- portée « motif » : elle devient une règle apprise appliquée à tous les constats partageant la même
  signature (même champ + même motif détecté), lors de cette exécution et des suivantes.
Les corrections alimentent aussi l'entraînement du modèle de scoring (poids ×5).
"""
from __future__ import annotations

import datetime as dt
import json
import threading
from pathlib import Path

from ..models import LEVEL_EXPERT, VERDICTS

ROOT = Path(__file__).resolve().parents[2]
FEEDBACK_PATH = ROOT / "output" / "feedback.json"
_lock = threading.Lock()


class FeedbackStore:
    def __init__(self, path: Path = FEEDBACK_PATH):
        self.path = path

    def load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []
        except (json.JSONDecodeError, OSError):
            return []

    def add(self, finding, verdict: str, commentaire: str, portee: str = "cas", auteur: str = "expert") -> dict:
        if verdict not in VERDICTS:
            raise ValueError(f"Verdict invalide : {verdict}")
        if portee not in ("cas", "motif"):
            raise ValueError("Portée invalide (cas | motif)")
        entry = {"finding_id": finding.id, "champ_b": finding.champ_b, "signature": finding.signature,
                 "verdict_initial": finding.verdict, "verdict": verdict, "commentaire": commentaire, "portee": portee,
                 "auteur": auteur, "date": dt.datetime.now().isoformat(timespec="seconds")}
        with _lock:
            data = self.load()
            data = [d for d in data if not (d["finding_id"] == finding.id and d["portee"] == portee)]
            data.append(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return entry

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def apply(self, findings) -> set[str]:
        """Applique les corrections ; retourne les identifiants des constats corrigés."""
        data = self.load()
        by_id = {d["finding_id"]: d for d in data if d["portee"] == "cas"}
        by_sig = {d["signature"]: d for d in data if d["portee"] == "motif" and d["signature"]}
        touched = set()
        for f in findings:
            d = by_id.get(f.id) or by_sig.get(f.signature)
            if not d:
                continue
            origine = "correction expert" if d["finding_id"] == f.id else f"règle apprise (motif « {d['signature']} »)"
            f.ia["avant_expert"] = {"verdict": f.verdict, "decide_par": f.decide_par, "justification": f.justification}
            f.verdict = d["verdict"]
            f.niveau = LEVEL_EXPERT
            f.decide_par = f"Expert — {origine}"
            f.justification = f"{d['commentaire'] or 'Verdict corrigé par un expert.'} (par {d['auteur']}, {d['date']})"
            f.confiance = 1.0
            f.a_valider = False
            touched.add(f.id)
        return touched
