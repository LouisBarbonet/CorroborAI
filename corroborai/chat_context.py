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
        "arbitrer les écarts qu'aucune règle ne tranche (heures), (b) pour diagnostiquer "
        "la cause probable des anomalies, (c) pour prioriser (scikit-learn), (d) pour rédiger la synthèse par cause racine "
        "(Gemini), (e) pour calibrer une règle ambiguë contre les données, et (f) pour apprendre des corrections des experts. "
        "Si le LLM contredit l'analyse locale, le cas est marqué « à valider ». Sans LLM, un gabarit local prend le relais.",
        "Priorité d'une anomalie (0-100) = 100 × (0,50 × criticité métier du champ + 0,25 × confiance + 0,10 × P(anomalie) "
        "du modèle ML + 0,10 × atypicité IsolationForest + 0,05 × concentration d'anomalies chez le même employé).",
        "« À valider » : verdict IA de confiance modérée, ou désaccord entre l'analyse locale et le LLM, ou règle non applicable "
        "au cas ; un expert fonctionnel doit confirmer. La correction expert peut viser un cas ou tous les cas du même motif.",
        "Courriel [R-EMAIL] : précision de Loto-Québec, le « code » de la règle est le matricule (personId) et le préfixe "
        "d'environnement (ex. « dev-08-v2_ ») peut être ajouté côté destination : il est accepté. Les 22 adresses de "
        "destination respectent la structure de la règle mais utilisent un identifiant différent du matricule : anomalies "
        "de faible priorité. Loto-Québec a confirmé qu'il s'agit d'une erreur d'anonymisation du jeu de test et a souhaité "
        "que ce cas soit inclus dans la détermination des anomalies (en production, ce serait une erreur de construction du courriel).",
        "Libellé de rôle [R-POSNAME] : précision de Loto-Québec, un libellé dont le préfixe ne correspond pas au code emploi "
        "(ex. code 6203 : « 4367-Empl4367 » au lieu de « 6203-Empl6203 ») est une erreur à signaler comme écart : anomalies de "
        "faible priorité (substitution systématique détectée sur tout le jeu).",
        "Date d'effet de l'affectation [R-ASSIGN-START] : précision de Loto-Québec, le champ source ne porte que la date d'effet "
        "du poste, la destination applique la règle transformée (date la plus récente entre la date d'effet du poste et celle "
        "du détail de poste courant) ; les écarts correspondants (ex. 9989151, 4402456, 3241002) sont donc justifiés.",
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
    anomalies = [f for f in res.findings if f.verdict == ANOMALIE]
    groups_def = {"email:identifiant_different_matricule": ("Courriels", "R-EMAIL",
                                                            "cause confirmée : erreur d'anonymisation du jeu de test"),
                  "posname:substitution_systematique": ("Libellés de rôle (positionName)", "R-POSNAME",
                                                        "erreur confirmée par Loto-Québec, substitution systématique")}
    grouped_all = {sig: [f for f in anomalies if f.signature == sig] for sig in groups_def}
    in_group = {f.id for items in grouped_all.values() for f in items}
    for f in anomalies:
        if f.id in in_group:
            continue
        flag = " — à valider par un expert" if f.a_valider else ""
        lines.append(f"- {ref(f)} {f.employe}, affectation {f.type_affectation}, poste {f.code_poste} ; règle [{f.regle_id}] ; "
                     f"attendu « {f.valeur_attendue} », reçu « {f.valeur_b} » ; priorité {f.priorite}{flag}. "
                     f"Cause : {_short(f.diagnostic or f.justification)}")
    for sig, (titre, regle, cause) in groups_def.items():
        grouped = grouped_all[sig]
        if not grouped:
            continue
        ex = grouped[0]
        lines.append(f"- {titre} ({len(grouped)} cas, règle [{regle}], {cause}, faible priorité "
                     f"{min(g.priorite for g in grouped)}-{max(g.priorite for g in grouped)}) : {' '.join(ref(g) for g in grouped)}. "
                     f"Exemple {ref(ex)} : attendu « {ex.valeur_attendue} », reçu « {ex.valeur_b} ». Cause : {_short(ex.diagnostic, 300)}")

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
        or (f.champ_b in ("weeklyHoursOverride", "dailyHoursOverride"))
        or (f.champ_b == "assignmentStartDate" and f.valeur_a != f.valeur_b))]
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
