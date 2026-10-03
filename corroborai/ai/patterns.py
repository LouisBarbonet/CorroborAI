"""Détecteurs locaux (IA symbolique / statistique) pour les écarts qu'aucune règle ne tranche.

Chaque détecteur retourne une proposition : verdict, confiance, signaux observés, justification
et une « signature » de motif (réutilisée par la boucle de rétroaction expert). Les détecteurs
raisonnent aussi à l'échelle du jeu de données complet (ex. cohérence d'une pseudonymisation).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .. import normalize as N
from .. import rules as R
from ..models import ANOMALIE, JUSTIFIE


@dataclass
class Proposal:
    verdict: str
    confiance: float
    signaux: list[str]
    justification: str
    signature: str
    a_valider: bool = False
    details: dict = field(default_factory=dict)


# ------------------------------------------------------------------ contexte global
def prepare(pairs) -> dict:
    """Statistiques transverses : correspondances code d'emploi ↔ libellé cible, courriels."""
    code_to_labels: dict[str, set] = defaultdict(set)
    label_to_codes: dict[str, set] = defaultdict(set)
    emails_by_person: dict[str, set] = defaultdict(set)
    persons_by_email: dict[str, set] = defaultdict(set)
    for p in pairs:
        if p.src is None or p.dst is None:
            continue
        c = N.code(p.src.get("CodeEmploi"))
        lbl = N.text(p.dst.get("positionName"))
        if lbl:
            code_to_labels[c].add(lbl)
            label_to_codes[lbl].add(c)
        mat = N.code(p.src.get("Matricule"))
        em = N.email(p.dst.get("contactEmail"))
        if em:
            emails_by_person[mat].add(em)
            persons_by_email[em].add(mat)
    return {"code_to_labels": code_to_labels, "label_to_codes": label_to_codes,
            "emails_by_person": emails_by_person, "persons_by_email": persons_by_email}


# ------------------------------------------------------------------ détecteurs
_EMAIL_RE = re.compile(r"^(?:(?P<env>.+)_)?(?P<local>[^@_]+)(?P<domain>@.+)$")


def analyze_email(ctx: R.Ctx, exp: str, tgt: str | None, g: dict) -> Proposal:
    mat = N.code(ctx.src.get("Matricule"))
    if not tgt:
        return Proposal(ANOMALIE, 0.95, ["courriel absent dans la cible"], "Le courriel est vide dans le Système B.", "email:absent")
    m = _EMAIL_RE.match(tgt)
    exp_local, exp_domain = exp.split("@")[0], "@" + exp.split("@")[1]
    if not m:
        return Proposal(ANOMALIE, 0.9, ["format de courriel invalide"], f"« {tgt} » n'est pas une adresse valide.", "email:invalide")
    env, local, domain = m["env"], m["local"], m["domain"]
    sig, ok = [], True
    if env:
        sig.append(f"préfixe d'environnement « {env}_ » (environnement de test)")
    if domain != exp_domain:
        ok = False
        sig.append(f"domaine {domain} ≠ {exp_domain}")
    if local == exp_local:
        sig.append("partie locale identique à la règle")
        return Proposal(JUSTIFIE, 0.95, sig, "Seul un préfixe d'environnement technique est ajouté ; l'adresse respecte la règle.", "email:prefixe_env")
    if local[:1] != exp_local[:1]:
        ok = False
        sig.append(f"initiale « {local[:1]} » ≠ initiale du prénom « {exp_local[:1]} »")
    mm = re.fullmatch(r"([a-z]+?)(\d+)", local[1:])
    struct = False
    if mm:
        digits = mm[2]
        struct = len(digits) > 3 and digits[-3:] == digits[:-3][-3:]
        if struct:
            sig.append(f"structure « initiale + nom + identifiant ({digits[:-3]}) + 3 derniers chiffres ({digits[-3:]}) » respectée")
            if digits[:-3] != mat:
                sig.append(f"identifiant {digits[:-3]} ≠ matricule {mat} : pseudonymisation de l'identifiant")
    if not struct:
        ok = False
        sig.append("structure initiale + nom + 3 derniers chiffres non reconnue")
    shared = g["persons_by_email"].get(tgt, set()) - {mat}
    multi = g["emails_by_person"].get(mat, set()) - {tgt}
    if shared:
        ok = False
        sig.append(f"adresse partagée avec d'autres matricules : {sorted(shared)}")
    if multi:
        ok = False
        sig.append(f"plusieurs adresses pour le même matricule : {sorted(multi)}")
    if ok:
        return Proposal(JUSTIFIE, 0.8, sig,
                        "L'adresse suit la structure de la règle (initiale + nom + identifiant + 3 derniers chiffres, bon domaine), "
                        "est unique et stable par employé ; l'écart provient de l'anonymisation de l'identifiant et du préfixe d'environnement.",
                        "email:structure_conforme_anonymisee")
    return Proposal(ANOMALIE, 0.8, sig, "L'adresse ne respecte pas la structure attendue par la règle de construction du courriel.", "email:structure_non_conforme")


def analyze_position_name(ctx: R.Ctx, exp: str, tgt: str | None, g: dict) -> Proposal:
    code = N.code(ctx.src.get("CodeEmploi"))
    if not tgt:
        return Proposal(ANOMALIE, 0.95, ["libellé absent"], "positionName est vide dans le Système B.", "posname:absent")
    labels = g["code_to_labels"].get(code, set())
    codes = g["label_to_codes"].get(tgt, set())
    m = re.fullmatch(r"(\d+)-(.*?)(\d*)", tgt)
    sig = []
    fmt_ok = bool(m) and (not m[3] or m[3] == m[1])
    sig.append("format « code-libellé » cohérent en interne" if fmt_ok else "format « code-libellé » incohérent")
    bij = len(labels) == 1 and len(codes) == 1
    sig.append(f"emploi {code} ↦ {sorted(labels)} ; libellé ↦ emplois {sorted(codes)}")
    details = {"libelles_pour_ce_code": sorted(labels), "codes_pour_ce_libelle": sorted(codes)}
    if fmt_ok and bij:
        return Proposal(JUSTIFIE, 0.8, sig + ["correspondance bijective et stable sur tout le jeu de données"],
                        f"Le libellé « {tgt} » est la transcription pseudonymisée de « {exp} » : la correspondance code d'emploi ↔ libellé "
                        "est biunivoque sur l'ensemble des employés (anonymisation cohérente), la règle de concaténation est respectée.",
                        "posname:pseudonymisation_coherente", details=details)
    why = "plusieurs libellés pour un même emploi" if len(labels) > 1 else ("un libellé partagé par plusieurs emplois" if len(codes) > 1 else "format invalide")
    return Proposal(ANOMALIE, 0.85, sig, f"Incohérence du libellé d'emploi : {why}.", "posname:incoherent", details=details)


def analyze_hours(spec, ctx: R.Ctx, exp, tgt) -> Proposal:
    week, day = R.position_contract_hours(ctx)
    contract = week if spec.champ_b == "weeklyHoursOverride" else day
    details = {"heures_contrat_detail_poste": N.fmt(contract), "valeur_employe_source": N.fmt(exp), "valeur_cible": N.fmt(tgt)}
    if tgt is None:
        return Proposal(ANOMALIE, 0.85, ["valeur absente dans la cible"], "Heures absentes dans le Système B.", "hours:absent_cible", details=details)
    if exp is None and contract is not None and abs(tgt - contract) < 1e-6:
        return Proposal(JUSTIFIE, 0.85, ["source vide", f"cible = heures du contrat du poste ({N.fmt(contract)})"],
                        "La source ne précise pas d'heures pour l'employé ; le Système B applique les heures contractuelles du poste "
                        "(détail du poste) comme valeur par défaut.", "hours:defaut_poste_source_vide", details=details)
    if exp is not None and abs(tgt - exp) < 0.01:
        return Proposal(JUSTIFIE, 0.9, ["écart d'arrondi"], "Écart d'arrondi négligeable.", "hours:arrondi", details=details)
    if contract is not None and abs(tgt - contract) < 1e-6:
        return Proposal(ANOMALIE, 0.6, [f"source employé = {N.fmt(exp)}", f"cible = heures du contrat du poste ({N.fmt(contract)})"],
                        f"Le Système B conserve les heures contractuelles du poste ({N.fmt(contract)}) au lieu de la norme de l'employé "
                        f"({N.fmt(exp)}) : l'override ne semble pas transmis. À confirmer (un horaire réduit peut être géré autrement).",
                        "hours:override_non_transmis", a_valider=True, details=details)
    return Proposal(ANOMALIE, 0.9, ["valeur cible sans lien avec la source ni le poste"],
                    f"La valeur {N.fmt(tgt)} ne correspond ni à la source ({N.fmt(exp)}) ni au contrat du poste ({N.fmt(contract)}).",
                    "hours:valeur_inexpliquee", details=details)


def analyze_generic(spec, exp, tgt) -> Proposal:
    if exp is None or tgt is None:
        return Proposal(ANOMALIE, 0.85, ["valeur manquante d'un côté"], f"Valeur attendue {N.fmt(exp)!r}, reçue {N.fmt(tgt)!r}.", f"{spec.champ_b}:manquant")
    se, st = N.fmt(exp), N.fmt(tgt)
    fold = lambda s: re.sub(r"[\s\W_]+", "", (N.strip_accents(s) or "").casefold())
    if fold(se) == fold(st):
        return Proposal(JUSTIFIE, 0.85, ["différence de casse, d'accents ou de ponctuation uniquement"],
                        "Les valeurs sont équivalentes une fois la casse, les accents et la ponctuation normalisés.", f"{spec.champ_b}:casse_accents")
    if isinstance(exp, float) and isinstance(tgt, float) and exp and abs(exp - tgt) / abs(exp) < 0.01:
        return Proposal(JUSTIFIE, 0.7, ["écart numérique < 1 %"], "Écart numérique d'arrondi.", f"{spec.champ_b}:arrondi")
    ratio = SequenceMatcher(None, se, st).ratio()
    return Proposal(ANOMALIE, 0.8, [f"similarité {ratio:.2f}"], f"Valeur attendue « {se} », reçue « {st} ».", f"{spec.champ_b}:different")


def analyze(spec, ctx: R.Ctx, exp, tgt, g: dict) -> Proposal:
    if spec.champ_b == "contactEmail":
        return analyze_email(ctx, exp, tgt, g)
    if spec.champ_b == "positionName":
        return analyze_position_name(ctx, exp, tgt, g)
    if spec.champ_b in ("weeklyHoursOverride", "dailyHoursOverride"):
        return analyze_hours(spec, ctx, exp, tgt)
    return analyze_generic(spec, exp, tgt)


# ------------------------------------------------------------------ diagnostics des anomalies déterministes
def diagnose(spec, ctx: R.Ctx, exp, tgt, expectation) -> tuple[str, str]:
    """Retourne (diagnostic lisible, signature) expliquant la cause probable d'une anomalie."""
    b = spec.champ_b
    if b in ("assignmentStartDate", "assignmentEndDate", "termEndDate") and tgt is not None:
        tl = R.unit_timeline(ctx)
        effs = [h["DateEffet"] for h in tl["historique"]]
        if effs and tgt == effs[-1]:
            nuance = " (aucun changement d'unité adm. dans l'historique)" if not tl["changement"] else ""
            return (f"La cible reprend la date d'effet du DERNIER détail du poste {tl['poste']} ({N.fmt(tgt)}){nuance} "
                    f"au lieu de {N.fmt(exp)}. Cause probable : un changement non lié à l'unité administrative (gestionnaire, "
                    "poste secondaire…) a été propagé comme nouvelle date d'affectation.", f"{b}:dernier_effdt")
        if tgt in effs:
            return f"La valeur reçue correspond à une date d'effet intermédiaire du détail du poste ({N.fmt(tgt)}).", f"{b}:effdt_intermediaire"
        alt = expectation.evidence.get("valeur_regle_litterale_min")
        if alt and N.fmt(tgt) == alt:
            return "La valeur reçue correspond à la lecture littérale « date la plus ancienne » de la règle.", f"{b}:regle_min"
        return f"Date reçue {N.fmt(tgt)} sans correspondance avec la source ni le détail du poste.", f"{b}:inexpliquee"
    if b == "contractTypeCode":
        facts = expectation.evidence.get("faits_source", {})
        src_rules = [r for r in ctx.ref.contract_rules if r["code"] == N.fmt(tgt)]
        if src_rules:
            r = src_rules[0]
            return (f"Le code reçu {N.fmt(tgt)} correspond à la condition « {r['texte']} », alors que la source indique {facts} "
                    f"(→ {N.fmt(exp)}). Le type d'employé n'a pas été mis à jour ou a été mal dérivé.", f"{b}:{N.fmt(exp)}->{N.fmt(tgt)}")
        return f"Code {N.fmt(tgt)} inconnu de la table de correspondance du mapping.", f"{b}:code_inconnu"
    if b == "siteName" and tgt:
        num = re.findall(r"\d+", str(tgt))
        site = N.code(ctx.dst.get("siteCode")) if ctx.dst else None
        if num and site and num[-1].lstrip("0") != site:
            return (f"Le libellé reçu « {tgt} » correspond au site {num[-1]} alors que le code site est {site} (source et cible) : "
                    "incohérence code/libellé de l'emplacement dans le Système B.", f"{b}:libelle_autre_site")
    if b in ("statusReasonCode", "detailedStatus", "expectedReturnDate"):
        return (f"La situation d'emploi transmise ({N.fmt(tgt)}) ne correspond pas à celle dérivée de la source ({N.fmt(exp)}) : "
                "vérifier la jointure Motif / code de traitement des accès.", f"{b}:situation")
    return f"Valeur attendue « {N.fmt(exp)} » selon la règle, valeur reçue « {N.fmt(tgt)} ».", f"{b}:different"
