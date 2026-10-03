"""Apprentissage automatique (scikit-learn) : probabilité d'anomalie, confiance et priorité.

- Un modèle de régression logistique est entraîné à chaque exécution sur les verdicts *déterministes*
  (règles) et sur les corrections des experts (pondérées ×5). Il fournit une seconde opinion
  « P(anomalie) » pour les cas ambigus, indépendante des détecteurs de patterns.
- Un IsolationForest mesure l'atypicité de chaque anomalie (combinaison champ/valeurs rare).
- La priorité (0-100) combine criticité métier du champ, confiance, P(anomalie) et atypicité.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LogisticRegression

from ..models import ANOMALIE, JUSTIFIE, LEVEL_AI

FEATURES = ["criticite", "similarite", "meme_forme", "cible_vide", "attendu_vide", "ecart_numerique",
            "prefixe_commun", "suffixe_commun", "nb_signaux_justifiants"]


def _shape(s: str) -> str:
    return re.sub(r"[A-Za-zÀ-ÿ]+", "a", re.sub(r"\d+", "9", s))


def features(f) -> list[float]:
    e, t = f.valeur_attendue or "", f.valeur_b or ""
    sim = SequenceMatcher(None, e, t).ratio() if (e or t) else 1.0
    num = 0.0
    try:
        a, b = float(e), float(t)
        num = min(abs(a - b) / (abs(a) or 1.0), 1.0)
    except ValueError:
        pass
    pre = len(_common_prefix(e, t)) / max(len(e), len(t), 1)
    suf = len(_common_prefix(e[::-1], t[::-1])) / max(len(e), len(t), 1)
    just = sum(1 for s in f.ia.get("signaux", []) if any(k in s for k in ("respectée", "bijective", "cohérent", "défaut", "préfixe")))
    return [f.criticite, sim, float(_shape(e) == _shape(t)), float(not t), float(not e), num, pre, suf, float(just)]


def _common_prefix(a: str, b: str) -> str:
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[:i]


class Scorer:
    def __init__(self):
        self.model: LogisticRegression | None = None
        self.n_train = 0
        self.n_expert = 0

    def fit(self, findings, expert_ids: set[str]) -> None:
        X, y, w = [], [], []
        for f in findings:
            if f.valeur_attendue == f.valeur_b and f.id not in expert_ids:
                continue  # les cas strictement identiques n'apportent rien au modèle
            if f.niveau == LEVEL_AI and f.id not in expert_ids:
                continue  # on n'apprend pas de ses propres prédictions
            X.append(features(f))
            y.append(int(f.verdict == ANOMALIE))
            w.append(5.0 if f.id in expert_ids else 1.0)
        self.n_train, self.n_expert = len(X), sum(1 for f in findings if f.id in expert_ids)
        if len(set(y)) < 2:
            self.model = None
            return
        self.model = LogisticRegression(class_weight="balanced", max_iter=1000)
        self.model.fit(np.array(X), np.array(y), sample_weight=np.array(w))

    def proba_anomalie(self, f) -> float | None:
        if self.model is None:
            return None
        return float(self.model.predict_proba(np.array([features(f)]))[0, 1])

    def prioritize(self, findings) -> None:
        anomalies = [f for f in findings if f.verdict == ANOMALIE]
        rarity = {}
        if len(anomalies) >= 4:
            X = np.array([features(f) for f in anomalies])
            iso = IsolationForest(n_estimators=200, random_state=42).fit(X)
            scores = -iso.score_samples(X)
            lo, hi = scores.min(), scores.max()
            rarity = {f.id: float((s - lo) / (hi - lo)) if hi > lo else 0.5 for f, s in zip(anomalies, scores)}
        per_emp: dict[str, int] = {}
        for f in anomalies:
            per_emp[f.matricule] = per_emp.get(f.matricule, 0) + 1
        for f in findings:
            p = self.proba_anomalie(f)
            if p is not None:
                f.ia["ml_proba_anomalie"] = round(p, 3)
            if f.verdict == ANOMALIE:
                ml = p if p is not None else f.confiance
                score = 0.50 * f.criticite + 0.25 * f.confiance + 0.10 * ml + 0.10 * rarity.get(f.id, 0.5) \
                    + 0.05 * min(per_emp[f.matricule] / 4, 1.0)
                f.priorite = int(round(100 * score))
                f.ia["atypicite"] = round(rarity.get(f.id, 0.5), 3)
            elif f.verdict == JUSTIFIE and f.a_valider:
                f.priorite = int(round(40 * f.criticite + 20 * (1 - f.confiance)))
            else:
                f.priorite = 0

    def info(self) -> dict:
        return {"modele": "LogisticRegression + IsolationForest (scikit-learn)", "exemples_entrainement": self.n_train,
                "corrections_expert": self.n_expert, "actif": self.model is not None, "variables": FEATURES}
