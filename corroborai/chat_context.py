"""Contexte du chat du jury : règles, mapping, fonctionnement et résultats de la corroboration.

Le même texte alimente le serveur local (FastAPI) et le relais Cloudflare (embarqué au build dans
worker/src/data.generated.json) : la consigne est construite côté serveur, jamais par le navigateur.
Repères citables : [R-XXX] pour les règles, [matricule/champ] pour les constats.
"""
from __future__ import annotations

from collections import defaultdict

from .engine import Result
from .models import ANOMALIE, JUSTIFIE


def ref(f) -> str:
    return f"[{f.matricule}/{f.champ_b.strip('()')}]"


def _short(s: str | None, n: int = 260) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def citable_refs(res: Result) -> set[str]:
    return {ref(f) for f in res.findings} | {f"[{k}]" for k in res.meta["catalogue_regles"]} | {"[R-NORMALISATION]"}


def build_context(res: Result) -> str:
    m = res.meta
    c = res.counts()
    lines = [
        "## Projet",
        "CorroborIA compare l'extraction du Système A (RH) et celle du Système B (Temps) pour chaque champ du fichier "
        "Mapping.xlsx et classe chaque constat : Conforme (identique après normalisation), Écart justifié (différence "
        "expliquée par une règle métier, une normalisation ou une analyse IA) ou Anomalie (vraie erreur à investiguer).",
        "Pipeline : niveau 1 comparaison brute normalisée (dates sérielles Excel ↔ ISO, vides, encodage) ; niveau 2 règles "
        "métier du mapping (jointures Motif et Détail du poste) ; niveau 3 analyse IA des cas ambigus (détecteurs de "
        "patterns, scikit-learn LogisticRegression + IsolationForest pour la priorité, LLM Gemini avec repli automatique) ; "
        "enfin un expert peut corriger un verdict (cas ou motif) et la correction devient une règle apprise.",
        "Rôle de l'IA : les niveaux 1 et 2 sont 100 % déterministes (aucune IA). L'IA intervient (a) au niveau 3 pour "
        "arbitrer les écarts qu'aucune règle ne tranche (courriels et libellés pseudonymisés, heures), (b) pour diagnostiquer "
        "la cause probable des anomalies, (c) pour prioriser (scikit-learn), (d) pour rédiger la synthèse par cause racine "
        "(Gemini), (e) pour calibrer une règle ambiguë contre les données, et (f) pour apprendre des corrections des experts. "
        "Si le LLM contredit l'analyse locale, le cas est marqué « à valider ». Sans LLM, un gabarit local prend le relais.",
        "Priorité d'une anomalie (0-100) = 100 × (0,50 × criticité métier du champ + 0,25 × confiance + 0,10 × P(anomalie) "
        "du modèle ML + 0,10 × atypicité IsolationForest + 0,05 × concentration d'anomalies chez le même employé).",
        "« À valider » : verdict IA de confiance modérée, ou désaccord entre l'analyse locale et le LLM, ou règle non applicable "
        "au cas ; un expert fonctionnel doit confirmer. La correction expert peut viser un cas ou tous les cas du même motif.",
        "Les fichiers sources sont en lecture seule (contrôle sha256). Le LLM ne reçoit que des valeurs anonymisées minimales.",
        "",
        "## Résultats sur les extractions fournies",
        f"{c['total']} constats ({m['nb_lignes']['source']} affectations source, {m['nb_lignes']['destination']} lignes cible) : "
        f"{c[ANOMALIE]} anomalies, {c[JUSTIFIE]} écarts justifiés, {c['Conforme']} conformes, {c['a_valider']} à valider par un expert.",
    ]
    for cal in m.get("calibration_regles", []):
        lines.append(f"Calibration [{cal['regle']}] : texte du mapping {cal['texte_mapping']} ; concordance avec le Système B "
                     f"{cal['interpretations']} ; interprétation retenue « {cal['retenue']} ». {cal['conclusion']}")
    synth = m.get("synthese", {})
    if synth.get("resume"):
        lines.append(f"Synthèse : {_short(synth['resume'], 700)}")

    lines += ["", "## Anomalies (par priorité)"]
    for f in [f for f in res.findings if f.verdict == ANOMALIE]:
        flag = " — à valider par un expert" if f.a_valider else ""
        lines.append(f"- {ref(f)} {f.employe}, affectation {f.type_affectation}, poste {f.code_poste} ; règle [{f.regle_id}] ; "
                     f"attendu « {f.valeur_attendue} », reçu « {f.valeur_b} » ; priorité {f.priorite}{flag}. "
                     f"Cause : {_short(f.diagnostic or f.justification)}")

    lines += ["", "## Écarts justifiés (regroupés)"]
    groups: dict[tuple, list] = defaultdict(list)
    for f in [f for f in res.findings if f.verdict == JUSTIFIE]:
        groups[(f.champ_b, f.regle_id, f.decide_par.split(" (")[0])].append(f)
    for (champ, regle, par), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        ex = items[0]
        lines.append(f"- {champ} : {len(items)} cas, règle [{regle}], décidé par {par}. Exemple {ref(ex)} : "
                     f"A « {_short(ex.valeur_a, 80)} », B « {_short(ex.valeur_b, 80)} ». {_short(ex.justification, 220)}")

    notable = [f for f in res.findings if f.verdict == JUSTIFIE and (
        (f.regle_id.startswith("R-STATUS") and f.valeur_attendue not in (None, "")) or f.regle_id == "R-NORMALISATION"
        or (f.champ_b in ("weeklyHoursOverride", "dailyHoursOverride")))]
    if notable:
        lines += ["", "## Écarts justifiés notables (détail)"]
        for f in notable:
            lines.append(f"- {ref(f)} {f.employe} : A « {_short(f.valeur_a, 80)} », attendu « {f.valeur_attendue} », "
                         f"B « {_short(f.valeur_b, 80)} » ; règle [{f.regle_id}]. {_short(f.justification, 240)}")

    lines += ["", "## Règles (catalogue)"]
    lines += [f"- [{k}] {v}" for k, v in m["catalogue_regles"].items()]
    lines.append("- [R-NORMALISATION] Valeur identique après réparation de l'encodage (ex. « Absence complÃ¨te » = « Absence complète »).")

    lines += ["", "## Mapping (Mapping.xlsx)"]
    for r in m["couverture_mapping"]:
        lines.append(f"- ligne {r['ligne_excel']} : {r['champ_a']} → {r['champ_b']} ({r['statut']})")
    return "\n".join(lines)
