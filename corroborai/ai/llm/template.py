"""Repli final, toujours disponible : verdicts et justifications construits à partir de l'analyse locale."""
from __future__ import annotations

from .base import Provider


class TemplateProvider(Provider):
    name = "gabarit-local"
    model = ""
    local = True

    def available(self) -> tuple[bool, str]:
        return True, "toujours disponible (aucun appel externe)"

    def complete_json(self, system: str, user: str, schema: dict) -> dict:  # pragma: no cover - non utilisé directement
        raise NotImplementedError("Le gabarit est appliqué directement par le routeur.")

    @staticmethod
    def judge(cases: list[dict]) -> dict:
        return {"cas": [{"id": c["id"], "verdict": c["analyse_locale"]["verdict"], "confiance": c["analyse_locale"]["confiance"],
                         "justification": c["analyse_locale"]["justification"]} for c in cases]}

    RECO = {
        "manquant": ("Affectation absente du Système B",
                     "Vérifier le flux d'interface pour les affectations temporaires/secondaires et relancer leur création."),
        "code_contrat_incorrect": ("Type d'employé mal dérivé",
                                   "Recalculer contractTypeCode depuis EMPTP_CD / PERM_IND / FT_IND (table du mapping) et corriger les employés listés."),
        "dernier_effdt": ("Date d'affectation reprise du dernier détail du poste",
                          "Appliquer la règle de l'unité administrative : ignorer les changements de détail sans changement d'unité."),
        "libelle_autre_site": ("Libellé d'emplacement incohérent avec le code site",
                               "Resynchroniser siteName à partir de siteCode dans le Système B."),
        "identifiant_different_matricule": ("Courriel construit avec un identifiant autre que le matricule",
                                            "Préfixe d'environnement accepté ; identifiant ≠ matricule. Cause confirmée par Loto-Québec : "
                                            "erreur d'anonymisation du jeu de test (en production : corriger la construction du courriel)."),
        "substitution_systematique": ("Libellé de rôle ne correspondant pas au code emploi",
                                      "Corriger la table de correspondance des libellés d'emploi (substitution systématique ; "
                                      "erreur confirmée par Loto-Québec)."),
        "override_non_transmis": ("Heures de l'employé non transmises (heures du poste conservées)",
                                  "Valider avec l'équipe fonctionnelle si l'override des heures doit être alimenté ; corriger le flux si oui."),
    }

    @staticmethod
    def summarize(stats: dict) -> dict:
        causes = []
        for grp in stats["groupes"]:
            titre, reco = TemplateProvider.RECO.get(grp["diagnostic_type"], (grp["diagnostic_type"], grp["exemple"]))
            causes.append({"cause": titre, "champs": [grp["champ"]], "nombre": grp["nombre"],
                           "recommandation": f"{reco} Matricules : {', '.join(grp['matricules'])}."})
        top = ", ".join(f"{g['champ']} ({g['nombre']})" for g in stats["groupes"][:4]) or "aucune"
        resume = (f"{stats['anomalies']} anomalie(s) réelle(s) à investiguer sur {stats['enregistrements']} affectations ; "
                  f"{stats['justifies']} écart(s) justifié(s) automatiquement. Principales zones : {top}.")
        return {"resume": resume, "causes_racines": causes}
