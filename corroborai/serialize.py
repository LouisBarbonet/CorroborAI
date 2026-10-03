"""Sérialisation JSON d'un résultat de corroboration.

Format unique partagé par l'API FastAPI, l'instantané embarqué dans le site statique et le moteur
exécuté dans le navigateur (Pyodide) : l'interface consomme exactement les mêmes structures partout.
"""
from __future__ import annotations

import json
from pathlib import Path

from .engine import Result

LIST_KEYS = ("id", "priorite", "verdict", "a_valider", "matricule", "employe", "type_affectation", "code_poste",
             "champ_a", "champ_b", "valeur_a", "valeur_attendue", "valeur_b", "niveau", "decide_par", "regle_id",
             "confiance", "justification")


def summary(res: Result) -> dict:
    m = res.meta
    return {"compteurs": res.counts(), "date_execution": m["date_execution"], "duree_s": m["duree_s"],
            "synthese": m["synthese"], "calibration_regles": m["calibration_regles"], "llm": m["llm"], "ml": m["ml"],
            "integrite": m["integrite"], "couverture_mapping": m["couverture_mapping"], "nb_lignes": m["nb_lignes"],
            "appariement": dict(m["appariement"]), "corrections_expert": m["corrections_expert"],
            "catalogue_regles": m["catalogue_regles"], "fichiers": {k: Path(v).name for k, v in m["fichiers"].items()},
            "champs": sorted({f.champ_b for f in res.findings})}


def finding_row(f) -> dict:
    return {k: getattr(f, k) for k in LIST_KEYS}


def to_payload(res: Result) -> dict:
    """Résultat complet : résumé + constats détaillés (preuves, analyse IA…)."""
    return {"summary": summary(res), "findings": [f.to_dict() for f in res.findings]}


def dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
