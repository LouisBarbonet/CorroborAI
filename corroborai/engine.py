"""Moteur de corroboration à 3 niveaux.

Niveau 1 — comparaison brute (après normalisation de format) ;
Niveau 2 — règles métier déterministes du mapping (jointures, dérivations, concaténations) ;
Niveau 3 — analyse IA des écarts que les règles ne tranchent pas (patterns locaux + ML + LLM avec repli).
Une correction d'expert peut ensuite surclasser n'importe quel verdict (traçée « Expert »).
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import normalize as N
from . import rules as R
from .ai import patterns as P
from .ai.feedback import FeedbackStore
from .ai.llm import LLMRouter
from .ai.scorer import Scorer
from .io_loader import Datasets, load
from .mapping import FIELD_SPECS, RULE_CATALOG, SOURCE_DISPLAY, FieldSpec, rule_text, validate_against_mapping
from .matcher import Pair, match
from .models import ANOMALIE, CONFORME, JUSTIFIE, LEVEL_AI, LEVEL_COMPARE, LEVEL_RULE, Finding


@dataclass
class Result:
    findings: list[Finding]
    meta: dict = field(default_factory=dict)

    def by_id(self, fid: str) -> Finding | None:
        return next((f for f in self.findings if f.id == fid), None)

    def counts(self) -> dict:
        c = Counter(f.verdict for f in self.findings)
        return {"total": len(self.findings), CONFORME: c[CONFORME], JUSTIFIE: c[JUSTIFIE], ANOMALIE: c[ANOMALIE],
                "a_valider": sum(f.a_valider for f in self.findings)}


def _eq(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-9
    return a == b


def _src_display(spec: FieldSpec, src: dict) -> str | None:
    cols = SOURCE_DISPLAY.get(spec.champ_b)
    if not cols:
        return N.fmt(N.normalize(src.get(spec.champ_a), spec.kind)) if spec.kind == "date" else N.raw_str(src.get(spec.champ_a))
    vals = [(c, N.raw_str(src.get(c)) if "Date" not in c else N.fmt(N.to_date(src.get(c)))) for c in cols]
    if len(vals) == 1:
        return vals[0][1]
    return " | ".join(f"{c}={v if v is not None else '∅'}" for c, v in vals)


def _employee(src: dict | None, dst: dict | None) -> str:
    if src:
        return f"{N.text(src.get('PrénomUsuel')) or ''} {N.text(src.get('NomFamille')) or ''}".strip()
    return f"{N.text(dst.get('givenName')) or ''} {N.text(dst.get('surname')) or ''}".strip()


class Engine:
    def __init__(self, router: LLMRouter | None = None, feedback: FeedbackStore | None = None, use_llm: bool = True):
        self.router = router or LLMRouter()
        self.feedback = feedback or FeedbackStore()
        self.use_llm = use_llm

    # ------------------------------------------------------------------ API publique
    def run(self, paths: dict[str, Path] | None = None, data_dir: Path | None = None, ds: Datasets | None = None) -> Result:
        started = dt.datetime.now()
        ds = ds or load(paths, data_dir)
        ref = R.build_refdata(ds)
        pairs = match(ds.source, ds.destination)
        g = P.prepare(pairs)
        findings: list[Finding] = []
        pending: list[tuple[Finding, P.Proposal]] = []

        for pair in pairs:
            if pair.src is None or pair.dst is None:
                findings.append(self._record_finding(pair, ds))
                continue
            ctx = R.Ctx(pair.src, pair.dst, ref)
            for spec in FIELD_SPECS:
                f, prop = self._evaluate(spec, ctx, pair, ref, g)
                findings.append(f)
                if prop is not None:
                    pending.append((f, prop))

        llm_used = self._resolve_ambiguous(pending)
        expert_ids = self.feedback.apply(findings)
        scorer = Scorer()
        scorer.fit(findings, expert_ids)
        scorer.prioritize(findings)
        findings.sort(key=lambda f: ({ANOMALIE: 0, JUSTIFIE: 1, CONFORME: 2}[f.verdict], -f.priorite, f.matricule, f.champ_b))

        res = Result(findings)
        res.meta = {
            "date_execution": started.isoformat(timespec="seconds"),
            "duree_s": None,
            "fichiers": {k: str(v) for k, v in ds.paths.items()},
            "integrite": ds.integrity,
            "couverture_mapping": validate_against_mapping(ds.mapping),
            "appariement": Counter(p.methode for p in pairs),
            "nb_lignes": {"source": len(ds.source), "destination": len(ds.destination),
                          "detail_poste": len(ds.detail), "motif": len(ds.motif)},
            "calibration_regles": self._calibrate(pairs, ref),
            "llm": {**self.router.status(), "utilise": llm_used, "trace": self.router.trace[-20:],
                    "reponses_cache": self.router.cache_hits},
            "ml": scorer.info(),
            "corrections_expert": len(expert_ids),
            "catalogue_regles": RULE_CATALOG,
            "regles_contrat": ref.contract_rules,
            "regles_situation": [{**r, "codes": sorted(r["codes"])} for r in ref.situation_rules],
        }
        res.meta["synthese"] = self._summary(res)
        res.meta["compteurs"] = res.counts()
        res.meta["duree_s"] = round((dt.datetime.now() - started).total_seconds(), 2)
        return res

    # ------------------------------------------------------------------ niveaux 1 et 2
    def _evaluate(self, spec: FieldSpec, ctx: R.Ctx, pair: Pair, ref: R.RefData, g: dict):
        src, dst = pair.src, pair.dst
        exp = spec.rule(ctx)
        tgt_raw = dst.get(spec.champ_b)
        tgt = N.normalize(tgt_raw, spec.kind)
        src_disp = _src_display(spec, src)
        mat, poste = N.code(src.get("Matricule")), N.code(src.get("CodePoste"))
        f = Finding(
            id=f"{mat}|{poste}|{spec.champ_b}", matricule=mat, employe=_employee(src, dst), code_poste=poste,
            code_emploi=N.code(src.get("CodeEmploi")), type_affectation=N.code(src.get("TypeAffectation")),
            description=(ref.mapping_by_b.get(spec.mapping_key) or {}).get("description") or spec.champ_b,
            champ_a=spec.champ_a, champ_b=spec.champ_b, valeur_a=src_disp, valeur_b=N.raw_str(tgt_raw),
            valeur_attendue=N.fmt(exp.expected), verdict=CONFORME, niveau=LEVEL_COMPARE, regle_id=spec.regle_id,
            regle_texte=rule_text(spec, ref.mapping_by_b), decide_par="Comparaison", justification="",
            preuves={"regle": exp.explanation, **exp.evidence, "appariement": pair.methode,
                     "valeur_b_normalisee": N.fmt(tgt)},
            criticite=spec.criticite,
        )
        if exp.covered and _eq(exp.expected, tgt):
            raw_identical = N.raw_str(src.get(spec.champ_a)) == N.raw_str(tgt_raw) and spec.champ_a in src
            if N.has_mojibake(tgt_raw):
                f.verdict, f.niveau, f.decide_par = JUSTIFIE, LEVEL_RULE, "Règle (normalisation)"
                f.regle_id = "R-NORMALISATION"
                f.justification = (f"Valeur identique après correction de l'encodage : « {N.raw_str(tgt_raw)} » (UTF-8 lu comme Latin-1) "
                                   f"= « {N.fmt(tgt)} ». {exp.explanation}")
                f.diagnostic = "Défaut d'encodage dans l'extraction du Système B (sans impact sur la valeur) : à corriger dans l'export."
                f.signature = f"{spec.champ_b}:encodage"
            elif exp.transformed:
                f.verdict, f.niveau, f.decide_par = JUSTIFIE, LEVEL_RULE, "Règle métier"
                f.justification = f"Écart expliqué par la règle {spec.regle_id} : {exp.explanation}"
                f.signature = f"{spec.champ_b}:regle"
            elif raw_identical:
                f.justification = "Valeurs identiques dans les deux systèmes."
            else:
                f.justification = f"Valeurs identiques après normalisation du format ({spec.kind}) : « {f.valeur_a} » ≡ « {f.valeur_b} »."
            return f, None

        if exp.covered and not spec.ai_eligible:
            diag, sig = P.diagnose(spec, ctx, exp.expected, tgt, exp)
            f.verdict, f.niveau, f.decide_par, f.confiance = ANOMALIE, LEVEL_RULE, "Règle métier", 0.97
            f.justification = (f"Non-respect de la règle {spec.regle_id} : valeur attendue « {N.fmt(exp.expected)} », "
                               f"reçue « {N.fmt(tgt)} ». {exp.explanation}")
            f.diagnostic, f.signature = diag, sig
            # Diagnostic de structure (détecteurs de patterns) pour les règles précisées par Loto-Québec :
            # confiance, signaux et cause probable, sans arbitrage LLM du verdict.
            refine = {"contactEmail": (lambda: P.assess_email(ctx, exp.expected, g), "Règle métier (préfixe optionnel accepté)"),
                      "positionName": (lambda: P.analyze_position_name(ctx, exp.expected, tgt, g), "Règle métier + diagnostic IA")}
            if spec.champ_b in refine:
                make, par = refine[spec.champ_b]
                prop = make()
                f.confiance, f.a_valider, f.signature, f.diagnostic = prop.confiance, prop.a_valider, prop.signature, prop.justification
                f.ia = {"signaux": prop.signaux, **prop.details}
                f.decide_par = par
            return f, None

        prop = P.analyze(spec, ctx, exp.expected, tgt, g)
        f.niveau, f.decide_par = LEVEL_AI, "IA locale"
        f.verdict, f.confiance, f.justification = prop.verdict, prop.confiance, prop.justification
        f.signature, f.a_valider = prop.signature, prop.a_valider
        f.ia = {"signaux": prop.signaux, "analyse_locale": {"verdict": prop.verdict, "confiance": prop.confiance,
                                                            "justification": prop.justification}, **prop.details}
        if not exp.covered:
            f.ia["signaux"].insert(0, "règle non applicable à ce cas : " + exp.explanation)
            f.a_valider = True
        if prop.verdict == ANOMALIE:
            f.diagnostic = prop.justification
        return f, prop

    def _record_finding(self, pair: Pair, ds: Datasets) -> Finding:
        if pair.dst is None:
            s = pair.src
            mat, poste = N.code(s.get("Matricule")), N.code(s.get("CodePoste"))
            others = [d for d in ds.destination.to_dict("records") if N.code(d.get("personId")) == mat]
            t = N.code(s.get("TypeAffectation"))
            label = {"P": "primaire", "A": "temporaire", "S": "secondaire"}.get(t, t)
            diag = (f"L'employé existe dans le Système B ({len(others)} affectation(s) transmise(s)) mais son affectation {label} "
                    f"(poste {poste}, emploi {N.code(s.get('CodeEmploi'))}, entrée {N.fmt(N.to_date(s.get('DateEntréePoste')))}) est absente."
                    if others else "L'employé est totalement absent du Système B.")
            return Finding(
                id=f"{mat}|{poste}|(affectation)", matricule=mat, employe=_employee(s, None), code_poste=poste,
                code_emploi=N.code(s.get("CodeEmploi")), type_affectation=t, description="Existence de l'affectation",
                champ_a="(enregistrement)", champ_b="(affectation)", valeur_a=f"Affectation {t} — poste {poste}", valeur_b=None,
                valeur_attendue="1 enregistrement", verdict=ANOMALIE, niveau=LEVEL_RULE, regle_id="R-RECORD",
                regle_texte=RULE_CATALOG["R-RECORD"], decide_par="Règle métier", confiance=0.99,
                justification=f"Enregistrement manquant dans le Système B. {diag}", diagnostic=diag,
                preuves={"appariement": pair.methode, "affectations_B_meme_matricule": len(others)},
                criticite=1.0, signature="record:manquant")
        d = pair.dst
        pid = N.code(d.get("personId"))
        return Finding(
            id=f"{pid}|B{pair.dst_index}|(affectation)", matricule=pid, employe=_employee(None, d), code_poste=None,
            code_emploi=N.code(d.get("positionId")), type_affectation=None, description="Existence de l'affectation",
            champ_a="(enregistrement)", champ_b="(affectation)", valeur_a=None,
            valeur_b=f"emploi {N.code(d.get('positionId'))}", valeur_attendue="aucun enregistrement", verdict=ANOMALIE,
            niveau=LEVEL_RULE, regle_id="R-RECORD", regle_texte=RULE_CATALOG["R-RECORD"], decide_par="Règle métier",
            confiance=0.95, justification="Enregistrement présent dans le Système B sans équivalent dans la source RH.",
            diagnostic="Affectation orpheline dans le Système B (doublon ou affectation non fermée).",
            preuves={"appariement": pair.methode}, criticite=0.9, signature="record:surplus")

    # ------------------------------------------------------------------ niveau 3
    def _resolve_ambiguous(self, pending: list[tuple[Finding, P.Proposal]]) -> list[str]:
        if not pending:
            return []
        used = set()
        groups: dict[str, list[tuple[Finding, P.Proposal]]] = defaultdict(list)
        for f, p in pending:
            groups[f.champ_b].append((f, p))
        for champ, items in groups.items():
            cases = [{"id": f.id, "valeur_systeme_A": f.valeur_a, "valeur_attendue_selon_regle": f.valeur_attendue,
                      "valeur_systeme_B": f.valeur_b,
                      "analyse_locale": {"verdict": p.verdict, "confiance": p.confiance, "signaux": p.signaux,
                                         "justification": p.justification}} for f, p in items]
            if self.use_llm:
                decisions, provider = self.router.judge(champ, items[0][0].regle_texte, cases)
            else:
                decisions, provider = {}, "gabarit-local"
            used.add(provider)
            for f, p in items:
                self._merge(f, p, decisions.get(f.id), provider)
        return sorted(used)

    @staticmethod
    def _merge(f: Finding, p: P.Proposal, llm: dict | None, provider: str) -> None:
        if not llm or provider.startswith("gabarit"):
            f.decide_par = "IA locale (patterns + ML)"
            return
        f.ia["llm"] = {"fournisseur": provider, **llm}
        if llm["verdict"] == p.verdict:
            f.confiance = round(max(p.confiance, (p.confiance + llm["confiance"]) / 2), 3)
            f.decide_par = f"IA — patterns locaux + LLM ({provider})"
            f.justification = llm["justification"] or p.justification
            return
        f.a_valider = True
        f.ia["desaccord"] = True
        if p.confiance >= 0.75 or llm["confiance"] < 0.6:
            f.decide_par = f"IA locale (LLM {provider} en désaccord)"
            f.justification = f"{p.justification} — Avis LLM divergent : {llm['justification']}"
            f.confiance = round(min(p.confiance, 1 - llm["confiance"] / 2), 3)
        else:
            f.verdict = llm["verdict"]
            f.decide_par = f"IA — LLM ({provider}), analyse locale divergente"
            f.justification = f"{llm['justification']} — Analyse locale divergente : {p.justification}"
            f.confiance = round(min(llm["confiance"], 1 - p.confiance / 2), 3)
            f.diagnostic = f.justification if f.verdict == ANOMALIE else ""

    # ------------------------------------------------------------------ méta-analyses
    @staticmethod
    def _calibrate(pairs: list[Pair], ref: R.RefData) -> list[dict]:
        """Confronte les interprétations possibles d'une règle ambiguë aux données (aide à la décision)."""
        hits = Counter()
        n = 0
        for p in pairs:
            if p.src is None or p.dst is None:
                continue
            ctx = R.Ctx(p.src, p.dst, ref)
            ev = R.rule_assignment_start(ctx).evidence
            tgt = N.fmt(N.to_date(p.dst.get("assignmentStartDate")))
            n += 1
            hits["min"] += ev.get("valeur_regle_litterale_min", ev["DateEntréePoste"]) == tgt
            hits["max"] += ev.get("valeur_interpretation_max", ev["DateEntréePoste"]) == tgt
            hits["detail"] += ev.get("valeur_regle_transformee", ev["DateEntréePoste"]) == tgt
        best = max(("detail", "max", "min"), key=lambda k: hits[k])
        labels = {"min": "littérale (plus ancienne, unité adm.)", "max": "plus récente (unité adm.)",
                  "detail": "règle transformée (plus récente, détail de poste courant)"}
        return [{
            "regle": "R-ASSIGN-START", "texte_mapping": "« Date la plus ancienne entre la date calculée du changement d'unité "
                                                       "administrative et la date d'effet poste »",
            "interpretations": {labels[k]: f"{hits[k]}/{n}" for k in ("min", "max", "detail")},
            "retenue": ref.assign_start_mode,
            "conclusion": (f"Interprétation retenue : {labels[ref.assign_start_mode]} ({hits[ref.assign_start_mode]}/{n}). "
                           "Loto-Québec a confirmé que la source ne porte que la date d'effet du poste et que la destination "
                           "applique la règle transformée (paramètre ASSIGN_START_MODE).")
            + ("" if best == ref.assign_start_mode else f" Attention : l'interprétation « {labels[best]} » concorde mieux."),
        }]

    def _summary(self, res: Result) -> dict:
        anomalies = [f for f in res.findings if f.verdict == ANOMALIE]
        groups: dict[tuple, list[Finding]] = defaultdict(list)
        for f in anomalies:
            sig = f.signature.split(":", 1)[-1] if f.signature else ""
            groups[(f.champ_b, "code_contrat_incorrect" if f.champ_b == "contractTypeCode" else sig)].append(f)
        stats = {
            "enregistrements": sum(1 for f in res.findings if f.champ_b == "personId") + sum(
                1 for f in res.findings if f.champ_b == "(affectation)"),
            "anomalies": len(anomalies), "justifies": sum(f.verdict == JUSTIFIE for f in res.findings),
            "conformes": sum(f.verdict == CONFORME for f in res.findings),
            # ordre d'importance : priorité maximale du groupe (et non le nombre de cas)
            "groupes": [{"champ": k[0], "diagnostic_type": k[1] or "écart", "nombre": len(v),
                         "matricules": sorted({f.matricule for f in v}), "exemple": v[0].diagnostic or v[0].justification}
                        for k, v in sorted(groups.items(), key=lambda kv: (-max(f.priorite for f in kv[1]), -len(kv[1])))],
        }
        if self.use_llm:
            out, provider = self.router.summarize(stats)
        else:
            from .ai.llm.template import TemplateProvider
            out, provider = TemplateProvider.summarize(stats), "gabarit-local"
        return {**out, "fournisseur": provider, "groupes": stats["groupes"]}


def run(paths: dict | None = None, data_dir: Path | None = None, use_llm: bool = True) -> Result:
    return Engine(use_llm=use_llm).run(paths, data_dir)
