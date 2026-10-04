"""Spécification déclarative des champs à corroborer, alignée sur Mapping.xlsx.

Seuls les champs présents dans le fichier de mapping sont corroborés. `validate_against_mapping`
vérifie au démarrage que chaque ligne du mapping est couverte (traçabilité).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from . import rules as R


@dataclass(frozen=True)
class FieldSpec:
    champ_b: str  # champ du Système B (Temps)
    champ_a: str  # champ(s) du Système A (RH) utilisés
    kind: str  # type de normalisation
    rule: Callable
    regle_id: str
    mapping_key: str  # valeur de la colonne « Système B » dans Mapping.xlsx
    ai_eligible: bool = False  # un écart peut-il être légitime hors règle (anonymisation, défauts…) ?
    criticite: float = 0.5  # impact métier d'une erreur (0-1) pour la priorisation


FIELD_SPECS: list[FieldSpec] = [
    FieldSpec("personId", "Matricule", "code", R.direct("Matricule", "code"), "R-DIRECT", "personId", criticite=1.0),
    FieldSpec("givenName", "PrénomUsuel", "text", R.direct("PrénomUsuel", "text"), "R-DIRECT", "givenName", True, 0.4),
    FieldSpec("surname", "NomFamille", "text", R.direct("NomFamille", "text"), "R-DIRECT", "surname", True, 0.4),
    # Règle clarifiée par Loto-Québec (code = matricule, préfixe optionnel) : décision déterministe, pas d'arbitrage LLM.
    FieldSpec("contactEmail", "PrénomUsuel + NomFamille + Matricule", "email", R.rule_email, "R-EMAIL", "contactEmail", False, 0.35),
    FieldSpec("onboardDate", "DateEmbaucheRécente", "date", R.direct("DateEmbaucheRécente", "date"), "R-DIRECT", "onboardDate", criticite=0.8),
    FieldSpec("siteName", "LibelléSite", "text", R.direct("LibelléSite", "text"), "R-DIRECT", "siteName", criticite=0.6),
    FieldSpec("siteCode", "CodeSite", "code", R.direct("CodeSite", "code"), "R-DIRECT", "siteCode", criticite=0.75),
    FieldSpec("divisionId", "CodeDirection", "code", R.direct("CodeDirection", "code"), "R-DIRECT", "divisionId", criticite=0.75),
    FieldSpec("divisionName", "CodeDirection + LibelléDirection", "text", R.rule_division_name, "R-DIVNAME", "divisionName", True, 0.5),
    FieldSpec("divisionCode", "CodeImputation", "code", R.direct("CodeImputation", "code"), "R-DIRECT", "divisionCode", criticite=0.75),
    FieldSpec("positionId", "CodeEmploi", "code", R.direct("CodeEmploi", "code"), "R-DIRECT", "positionId", criticite=0.8),
    FieldSpec("positionName", "CodeEmploi + IntituléEmploi", "text", R.rule_position_name, "R-POSNAME", "positionName", True, 0.45),
    FieldSpec("positionCode", "CodeEmploi", "code", R.direct("CodeEmploi", "code"), "R-DIRECT", "positionCode", criticite=0.8),
    FieldSpec("statusReasonCode", "CodeSuspensionAccès + CodeRaisonStatut (⋈ Motif)", "code", R.rule_status_reason, "R-STATUS-CAD", "statusReasonCode", criticite=0.95),
    FieldSpec("expectedReturnDate", "DateRetourAnticipée", "date", R.rule_expected_return, "R-STATUS-CADP", "expectedReturnDate", criticite=0.9),
    FieldSpec("detailedStatus", "CodeSuspensionAccès", "text", R.rule_detailed_status, "R-STATUS", "detailedStatus", criticite=0.95),
    FieldSpec("contractTypeCode", "CatégorieEmploi + EstPermanent + EstTempsPlein", "code", R.rule_contract, "R-CONTRACT", "contractTypeCode", criticite=0.9),
    FieldSpec("isPrimaryAssignment", "TypeAffectation", "bool", R.rule_primary, "R-AFFTYPE", "isPrimaryAssignment et isTemporaryAssignment", criticite=0.85),
    FieldSpec("isTemporaryAssignment", "TypeAffectation", "bool", R.rule_temporary, "R-AFFTYPE", "isPrimaryAssignment et isTemporaryAssignment", criticite=0.85),
    FieldSpec("assignmentStartDate", "DateEntréePoste (+ détail du poste)", "date", R.rule_assignment_start, "R-ASSIGN-START", "assignmentStartDate", criticite=0.8),
    FieldSpec("payGradeId", "ÉchelleSalariale", "code", R.direct("ÉchelleSalariale", "code"), "R-DIRECT", "payGradeId", criticite=0.85),
    FieldSpec("weeklyHoursOverride", "HeuresNormeHebdo", "num", R.direct("HeuresNormeHebdo", "num"), "R-DIRECT", "weeklyHoursOverride", True, 0.75),
    FieldSpec("dailyHoursOverride", "HeuresNormeQuotidienne", "num", R.direct("HeuresNormeQuotidienne", "num"), "R-DIRECT", "dailyHoursOverride", True, 0.75),
    FieldSpec("assignmentEndDate", "DateSortiePoste (+ détail du poste)", "date", R.rule_assignment_end, "R-ASSIGN-END", "assignmentEndDate", criticite=0.8),
    FieldSpec("termEndDate", "DateSortiePoste (+ détail du poste)", "date", R.rule_assignment_end, "R-ASSIGN-END", "termEndDate", criticite=0.7),
]

# Valeurs du Système A utilisées pour l'affichage « valeur source » des champs dérivés
SOURCE_DISPLAY = {
    "contactEmail": ["PrénomUsuel", "NomFamille", "Matricule"],
    "divisionName": ["CodeDirection", "LibelléDirection"],
    "positionName": ["CodeEmploi", "IntituléEmploi"],
    "statusReasonCode": ["CodeRaisonStatut"],
    "detailedStatus": ["CodeSuspensionAccès"],
    "contractTypeCode": ["CatégorieEmploi", "EstPermanent", "EstTempsPlein"],
    "isPrimaryAssignment": ["TypeAffectation"],
    "isTemporaryAssignment": ["TypeAffectation"],
    "assignmentStartDate": ["DateEntréePoste"],
    "assignmentEndDate": ["DateSortiePoste"],
    "termEndDate": ["DateSortiePoste"],
    "expectedReturnDate": ["DateRetourAnticipée"],
}

RULE_CATALOG = {
    "R-DIRECT": "Correspondance directe : valeur identique attendue après normalisation (format, vides, encodage).",
    "R-EMAIL": "Courriel = 1re lettre du prénom + nom + 3 derniers chiffres du matricule + @loto-quebec.com (sans accents).",
    "R-DIVNAME": "divisionName = Unité adm. (5 chiffres) + « - » + libellé de l'unité adm.",
    "R-POSNAME": "positionName = Emploi + « - » + description de l'emploi.",
    "R-STATUS": "Situation d'emploi : codes d'accès 00/01 → « Actif » ; 02/03/06/07 → « Absence complète ».",
    "R-STATUS-CAD": "statusReasonCode : null si actif ; sinon code Remphor obtenu par jointure CodeRaisonStatut ⋈ Motif.",
    "R-STATUS-CADP": "expectedReturnDate : null si actif ; sinon date de retour prévue.",
    "R-CONTRACT": "Type d'employé selon EMPTP_CD / PERM_IND / FT_IND (table du mapping).",
    "R-AFFTYPE": "P → primaire (true/false) ; A → temporaire (false/true) ; S → secondaire (false/false).",
    "R-ASSIGN-START": "Date d'effet de l'affectation : combinaison DateEntréePoste / date d'effet de l'unité adm. courante (détail du poste).",
    "R-ASSIGN-END": "Date de fin : plus ancienne entre expiration du poste et fin de l'unité adm. courante (effdt suivant − 1 j si l'unité change).",
    "R-RECORD": "Chaque affectation de la source doit exister une seule fois dans la cible (clé Matricule + Emploi + type d'affectation).",
}


def rule_text(spec: FieldSpec, mapping_by_b: dict) -> str:
    row = mapping_by_b.get(spec.mapping_key)
    txt = (row or {}).get("regle") or ""
    if not txt or txt.strip().upper() == "N/A":
        return RULE_CATALOG[spec.regle_id]
    return f"{txt.strip()} (Mapping.xlsx, ligne {row['ligne_excel']})"


def validate_against_mapping(mapping: pd.DataFrame) -> list[dict]:
    """Couverture du mapping : chaque champ B du fichier doit être corroboré (ou explicitement exclu)."""
    covered = {s.mapping_key for s in FIELD_SPECS}
    out = []
    for r in mapping.to_dict("records"):
        b = r["champ_b"]
        if b in covered:
            statut = "corroboré"
        elif b.strip() in ("-", ""):
            statut = "exclu (aucun champ cible dans le mapping)"
        else:
            statut = "NON COUVERT"
        out.append({"champ_a": r["champ_a"], "champ_b": b, "ligne_excel": r["ligne_excel"], "statut": statut})
    return out
