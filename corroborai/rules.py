"""Règles métier déterministes.

Chaque règle reçoit le contexte d'un enregistrement (ligne source, ligne cible, référentiels)
et retourne une `Expectation` : la valeur attendue dans le Système B, l'explication et les preuves
(lignes de jointure utilisées). Les paramètres des règles sont lus depuis Mapping.xlsx lorsque
c'est possible (types de contrat, codes de situation d'emploi) pour rester traçables.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from . import normalize as N
from .io_loader import Datasets
from .models import Expectation

EMAIL_DOMAIN = "@loto-quebec.com"
DIVISION_PAD = 5  # format observé « 00397-UnitAdmin00397 »


# ---------------------------------------------------------------- référentiels
@dataclass
class RefData:
    detail_by_poste: dict[str, list[dict]]
    motif_by_code: dict[str, dict]
    contract_rules: list[dict]
    situation_rules: list[dict]
    mapping_by_b: dict[str, dict]
    assign_start_mode: str = "detail"
    notes: list[str] = field(default_factory=list)


def _parse_contract_rules(rule_text: str) -> list[dict]:
    """Ex. 'SI PERM_IND=1 et FT_IND=1 et EMPTP_CD="V" --> Mettre "JWN"' → conditions + code."""
    out = []
    for line in rule_text.splitlines():
        m = re.search(r"SI\s+(.*?)\s*-->\s*Mettre\s*\"(\w+)\"", line, re.I)
        if not m:
            continue
        conds = dict((k.upper(), v.strip('"')) for k, v in re.findall(r"(\w+)\s*=\s*(\"?\w+\"?)", m[1]))
        label = re.search(r"\(([^)]*)\)", line)
        out.append({"conditions": conds, "code": m[2], "libelle": label[1] if label else "", "texte": line.strip()})
    return out


def _parse_situation_rules(df: pd.DataFrame) -> list[dict]:
    out = []
    for _, r in df.iterrows():
        vals = [None if N.is_null(v) else str(v).strip() for v in r.tolist()]
        if not vals or not vals[0]:
            continue
        codes = {int(c) for c in re.findall(r"\d+", vals[0])}
        label = (vals[1] or "").strip('"') if len(vals) > 1 else ""
        reason = vals[2] if len(vals) > 2 else None
        ret = vals[3] if len(vals) > 3 else None
        out.append({"codes": codes, "statut": N.text(label), "avec_raison": bool(reason and reason.lower() != "null"),
                    "avec_retour": bool(ret and ret.lower() != "null"), "texte": " | ".join(v or "null" for v in vals)})
    return out


def build_refdata(ds: Datasets) -> RefData:
    detail: dict[str, list[dict]] = {}
    for rec in ds.detail.to_dict("records"):
        detail.setdefault(N.code(rec["IdentifiantPoste"]), []).append(rec)
    for rows in detail.values():
        rows.sort(key=lambda r: N.to_date(r["DateEffetAffectation"]))
    motif = {N.code(r["CodeCatégorieStatut"]): r for r in ds.motif.to_dict("records")}
    mapping_by_b = {r["champ_b"]: r for r in ds.mapping.to_dict("records")}
    contract_txt = mapping_by_b.get("contractTypeCode", {}).get("regle", "")
    mode = os.environ.get("ASSIGN_START_MODE", "detail").lower()
    return RefData(detail, motif, _parse_contract_rules(contract_txt), _parse_situation_rules(ds.situation_rules),
                   mapping_by_b, assign_start_mode=mode if mode in ("detail", "max", "min") else "detail")


@dataclass
class Ctx:
    src: dict
    dst: dict | None
    ref: RefData


# ---------------------------------------------------------------- utilitaires
def _ev(*pairs) -> dict:
    return {k: N.fmt(v) if not isinstance(v, (list, dict)) else v for k, v in pairs}


def direct(src_field: str, kind: str):
    def rule(ctx: Ctx) -> Expectation:
        v = N.normalize(ctx.src.get(src_field), kind)
        return Expectation(v, f"Correspondance directe {src_field} → valeur identique attendue (après normalisation {kind}).")
    rule.__name__ = f"direct_{src_field}"
    return rule


# ---------------------------------------------------------------- règles du mapping
def rule_email(ctx: Ctx) -> Expectation:
    pre = N.strip_accents(N.text(ctx.src.get("PrénomUsuel")) or "")
    nom = N.strip_accents(N.text(ctx.src.get("NomFamille")) or "")
    mat = N.code(ctx.src.get("Matricule")) or ""
    nom_clean = re.sub(r"[^A-Za-z0-9]", "", nom)
    expected = f"{pre[:1]}{nom_clean}{mat[-3:]}{EMAIL_DOMAIN}".lower()
    prefix, _ = N.split_env_prefix(ctx.dst.get("contactEmail")) if ctx.dst else (None, None)
    expl = ("Première lettre du prénom + nom + 3 derniers chiffres du code de l'employé (matricule) + « @loto-quebec.com », "
            "accents retirés. Préfixe d'environnement optionnel accepté côté destination (précision de Loto-Québec)")
    expl += f" : préfixe « {prefix} » retiré avant comparaison." if prefix else "."
    return Expectation(expected, expl, _ev(("prenom", pre), ("nom", nom), ("matricule", mat), ("prefixe_destination", prefix)),
                       transformed=True)


def rule_division_name(ctx: Ctx) -> Expectation:
    c = N.code(ctx.src.get("CodeDirection"))
    lib = N.text(ctx.src.get("LibelléDirection"))
    if c is None or lib is None:
        return Expectation(None, "Unité administrative ou libellé absent dans la source.", covered=lib is None and c is None)
    exp = f"{c.zfill(DIVISION_PAD)}-{lib}"
    return Expectation(exp, f"Concaténation Unité adm. ({c} complété sur {DIVISION_PAD} chiffres) + « - » + libellé.",
                       _ev(("CodeDirection", c), ("LibelléDirection", lib)), transformed=True)


def rule_position_name(ctx: Ctx) -> Expectation:
    c = N.code(ctx.src.get("CodeEmploi"))
    lib = N.text(ctx.src.get("IntituléEmploi"))
    return Expectation(f"{c}-{lib}", "Concaténation Emploi + « - » + description de l'emploi.",
                       _ev(("CodeEmploi", c), ("IntituléEmploi", lib)), transformed=True)


def _situation(ctx: Ctx):
    code = N.code(ctx.src.get("CodeSuspensionAccès"))
    raison = N.code(ctx.src.get("CodeRaisonStatut"))
    motif = ctx.ref.motif_by_code.get(raison)
    rule = next((r for r in ctx.ref.situation_rules if code is not None and int(code) in r["codes"]), None)
    ev = {"CodeSuspensionAccès": code, "CodeRaisonStatut": raison, "CodeStatutEmploi": N.code(ctx.src.get("CodeStatutEmploi")),
          "jointure_motif": ({"CodeCatégorieStatut": raison, "CodeStatutSystèmeExterne (Remphor)": N.code(motif["CodeStatutSystèmeExterne"]),
                              "CodeGestionAccès": N.code(motif["CodeGestionAccès"])} if motif else "aucune ligne de motif"),
          "regle_situation": rule["texte"] if rule else "aucune règle pour ce code"}
    return code, raison, motif, rule, ev


def rule_detailed_status(ctx: Ctx) -> Expectation:
    code, _, _, rule, ev = _situation(ctx)
    if not rule:
        return Expectation(None, f"Code de traitement des accès « {code} » non couvert par le tableau de situation d'emploi.", ev, covered=False)
    return Expectation(rule["statut"], f"Code de traitement des accès {code} → cf_specificStatus « {rule['statut']} ».", ev, transformed=True)


def rule_status_reason(ctx: Ctx) -> Expectation:
    code, raison, motif, rule, ev = _situation(ctx)
    if not rule:
        return Expectation(None, f"Code de traitement des accès « {code} » non couvert.", ev, covered=False)
    if not rule["avec_raison"]:
        return Expectation(None, f"Situation « {rule['statut']} » (code {code}) → cf_CAD = null.", ev, transformed=True)
    if not motif:
        return Expectation(None, f"Absence : jointure motif impossible pour CodeRaisonStatut {raison}.", ev, covered=False)
    remphor = N.code(motif["CodeStatutSystèmeExterne"])
    gestion = N.code(motif["CodeGestionAccès"])
    expl = f"Absence (code {code}) → jointure Motif : CodeRaisonStatut {raison} → code Remphor {remphor}."
    if gestion != code:
        expl += f" Attention : CodeGestionAccès du motif ({gestion}) ≠ CodeSuspensionAccès source ({code})."
    return Expectation(remphor, expl, ev, transformed=True)


def rule_expected_return(ctx: Ctx) -> Expectation:
    code, _, _, rule, ev = _situation(ctx)
    ret = N.to_date(ctx.src.get("DateRetourAnticipée"))
    ev["DateRetourAnticipée"] = N.fmt(ret)
    if not rule:
        return Expectation(ret, f"Code de traitement des accès « {code} » non couvert.", ev, covered=False)
    if not rule["avec_retour"]:
        return Expectation(None, f"Situation « {rule['statut']} » → cf_CADP (date de retour) = null.", ev, transformed=ret is not None)
    return Expectation(ret, "Absence → cf_CADP = Date de retour prévue de la source.", ev)


def _flag(v) -> str | None:
    b = N.to_bool(v)
    return None if b is None else ("1" if b else "0")


def rule_contract(ctx: Ctx) -> Expectation:
    facts = {"EMPTP_CD": N.code(ctx.src.get("CatégorieEmploi")), "PERM_IND": _flag(ctx.src.get("EstPermanent")),
             "FT_IND": _flag(ctx.src.get("EstTempsPlein"))}
    for r in ctx.ref.contract_rules:
        if all(facts.get(k) == str(v).upper() for k, v in r["conditions"].items()):
            return Expectation(r["code"], f"{r['texte']}", {"faits_source": facts, "regle_appliquee": r["texte"]}, transformed=True)
    return Expectation(None, f"Aucune règle de type d'employé ne couvre {facts}.", {"faits_source": facts}, covered=False)


AFF_FLAGS = {"P": (True, False), "A": (False, True), "S": (False, False)}


def rule_primary(ctx: Ctx) -> Expectation:
    t = N.code(ctx.src.get("TypeAffectation"))
    if t not in AFF_FLAGS:
        return Expectation(None, f"Type d'affectation inconnu « {t} ».", covered=False)
    return Expectation(AFF_FLAGS[t][0], f"TypeAffectation={t} → isPrimaryAssignment={'true' if AFF_FLAGS[t][0] else 'false'}.", {"TypeAffectation": t}, transformed=True)


def rule_temporary(ctx: Ctx) -> Expectation:
    t = N.code(ctx.src.get("TypeAffectation"))
    if t not in AFF_FLAGS:
        return Expectation(None, f"Type d'affectation inconnu « {t} ».", covered=False)
    return Expectation(AFF_FLAGS[t][1], f"TypeAffectation={t} → isTemporaryAssignment={'true' if AFF_FLAGS[t][1] else 'false'}.", {"TypeAffectation": t}, transformed=True)


def unit_timeline(ctx: Ctx) -> dict:
    """Analyse l'historique du poste : date d'entrée en vigueur de l'unité adm. courante et fin éventuelle."""
    poste = N.code(ctx.src.get("CodePoste"))
    unit = N.code(ctx.src.get("CodeDirection"))
    rows = ctx.ref.detail_by_poste.get(poste, [])
    hist = [{"DateEffet": N.to_date(r["DateEffetAffectation"]), "Unité": N.code(r["CodeDirectionAffectée"]),
             "HeuresSemaine": N.to_num(r.get("HeuresSemaineContrat")), "HeuresJour": N.to_num(r.get("HeuresJourContrat"))} for r in rows]
    out = {"poste": poste, "unite_courante": unit, "historique": hist, "date_unite": None, "fin_unite": None, "changement": False}
    if not hist:
        return out
    idx = [i for i, h in enumerate(hist) if h["Unité"] == unit]
    if not idx:  # unité courante absente de l'historique : on se rabat sur la dernière unité connue
        idx = [len(hist) - 1]
    last = idx[-1]
    start = last
    while start > 0 and hist[start - 1]["Unité"] == hist[last]["Unité"]:
        start -= 1
    out["changement"] = start > 0
    out["date_unite"] = hist[start]["DateEffet"] if start > 0 else min(h["DateEffet"] for h in hist)
    if last + 1 < len(hist) and hist[last + 1]["Unité"] != hist[last]["Unité"]:
        out["fin_unite"] = hist[last + 1]["DateEffet"] - dt.timedelta(days=1)
    return out


def _hist_ev(tl: dict) -> list[dict]:
    return [{k: N.fmt(v) for k, v in h.items()} for h in tl["historique"]]


def rule_assignment_start(ctx: Ctx) -> Expectation:
    entree = N.to_date(ctx.src.get("DateEntréePoste"))
    tl = unit_timeline(ctx)
    du = tl["date_unite"]
    ev = {"DateEntréePoste": N.fmt(entree), "date_effet_unite_adm": N.fmt(du), "changement_unite_detecte": tl["changement"],
          "mode": ctx.ref.assign_start_mode, "historique_poste": _hist_ev(tl)}
    if du is None:
        return Expectation(entree, "Aucun détail de poste : la date d'entrée au poste est retenue.", ev)
    detail_courant = tl["historique"][-1]["DateEffet"]  # date d'effet du détail de poste courant
    cands = [d for d in (entree, du) if d]
    ev["date_effet_detail_courant"] = N.fmt(detail_courant)
    ev["valeur_regle_litterale_min"] = N.fmt(min(cands))
    ev["valeur_interpretation_max"] = N.fmt(max(cands))
    ev["valeur_regle_transformee"] = N.fmt(max(d for d in (entree, detail_courant) if d))
    mode = ctx.ref.assign_start_mode
    if mode == "detail":
        # Précision de Loto-Québec : la source ne porte que la date d'effet du poste ; la destination applique la règle
        # transformée, qui retient le détail de poste le plus récent.
        exp = max(d for d in (entree, detail_courant) if d)
        return Expectation(exp, f"Règle transformée (précisée par Loto-Québec) : date la plus récente entre la date d'effet du "
                                f"poste (DateEntréePoste {N.fmt(entree)}) et la date d'effet du détail de poste courant "
                                f"({N.fmt(detail_courant)}).", ev, transformed=exp != entree)
    exp = max(cands) if mode == "max" else min(cands)
    how = "la plus récente" if mode == "max" else "la plus ancienne"
    origin = "changement d'unité" if tl["changement"] else "MIN EFFDT (aucun changement d'unité)"
    return Expectation(exp, f"Date {how} entre DateEntréePoste ({N.fmt(entree)}) et la date d'effet de l'unité adm. "
                            f"{tl['unite_courante']} ({N.fmt(du)}, {origin}).", ev, transformed=exp != entree)


def rule_assignment_end(ctx: Ctx) -> Expectation:
    sortie = N.to_date(ctx.src.get("DateSortiePoste"))
    tl = unit_timeline(ctx)
    cands = [d for d in (sortie, tl["fin_unite"]) if d]
    exp = min(cands) if cands else None
    ev = {"DateSortiePoste": N.fmt(sortie), "fin_unite_adm": N.fmt(tl["fin_unite"]), "historique_poste": _hist_ev(tl)}
    expl = ("Aucune date de fin : pas de date d'expiration et l'unité adm. reste identique dans le détail du poste suivant (NULL)."
            if exp is None else f"Date la plus ancienne entre l'expiration du poste ({N.fmt(sortie)}) et la fin de l'unité adm. ({N.fmt(tl['fin_unite'])}).")
    return Expectation(exp, expl, ev, transformed=exp != sortie)


def position_contract_hours(ctx: Ctx) -> tuple[float | None, float | None]:
    tl = unit_timeline(ctx)
    if not tl["historique"]:
        return None, None
    last = tl["historique"][-1]
    return last["HeuresSemaine"], last["HeuresJour"]
