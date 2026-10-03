"""Tests de bout en bout sur les extractions fournies : chaque type de cas attendu est vérifié."""
from __future__ import annotations

import datetime as dt

import pytest

from corroborai import normalize as N
from corroborai.ai.feedback import FeedbackStore
from corroborai.engine import Engine
from corroborai.io_loader import DEFAULT_DATA_DIR, check_integrity
from corroborai.models import ANOMALIE, CONFORME, JUSTIFIE


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    fb = FeedbackStore(tmp_path_factory.mktemp("fb") / "feedback.json")
    return Engine(feedback=fb, use_llm=False).run()


def get(res, mat, champ, aff="P"):
    hits = [f for f in res.findings if f.matricule == mat and f.champ_b == champ and f.type_affectation == aff]
    assert hits, f"constat introuvable {mat} {champ}"
    return hits[0]


# ----------------------------------------------------------------- normalisation
def test_normalisation_dates():
    assert N.to_date(34739) == dt.date(1995, 2, 9)
    assert N.to_date("1995-02-09T00:00:00.000Z") == dt.date(1995, 2, 9)
    assert N.to_date(dt.datetime(1995, 2, 9)) == dt.date(1995, 2, 9)
    assert N.to_date(None) is None


def test_normalisation_encodage_et_codes():
    assert N.text("Absence complÃ¨te") == "Absence complète"
    assert N.has_mojibake("Absence complÃ¨te")
    assert N.code("00397") == "397" and N.code(40.0) == "40"
    assert N.to_bool("Oui") is True and N.to_bool("false") is False
    assert N.to_num("7,2") == 7.2


# ----------------------------------------------------------------- vraies anomalies
EXPECTED_ANOMALIES = {
    ("1545850", "(affectation)", "A"),
    ("2762457", "contractTypeCode", "P"), ("4625374", "contractTypeCode", "P"),
    ("3712987", "contractTypeCode", "P"), ("7254364", "contractTypeCode", "P"),
    ("6035643", "siteName", "P"), ("3241002", "siteName", "P"),
    ("9989151", "assignmentStartDate", "P"), ("4402456", "assignmentStartDate", "P"),
    ("3241002", "assignmentStartDate", "P"),
}


def test_anomalies_deterministes(result):
    found = {(f.matricule, f.champ_b, f.type_affectation) for f in result.findings if f.verdict == ANOMALIE}
    assert EXPECTED_ANOMALIES <= found
    for key in EXPECTED_ANOMALIES:
        f = get(result, key[0], key[1], key[2])
        assert f.justification and f.regle_id and f.diagnostic, f"verdict non expliqué : {key}"


def test_heures_override_signalees_a_valider(result):
    for mat in ("2911996", "4402456", "7683990"):
        f = get(result, mat, "weeklyHoursOverride")
        assert f.verdict == ANOMALIE and f.a_valider and f.niveau.startswith("3")


def test_aucune_anomalie_inattendue(result):
    allowed = EXPECTED_ANOMALIES | {(m, c, "P") for m in ("2911996", "4402456", "7683990")
                                    for c in ("weeklyHoursOverride", "dailyHoursOverride")}
    found = {(f.matricule, f.champ_b, f.type_affectation) for f in result.findings if f.verdict == ANOMALIE}
    assert found == allowed


def test_diagnostic_date_dernier_detail(result):
    f = get(result, "9989151", "assignmentStartDate")
    assert f.valeur_attendue == "2009-03-30" and f.signature.endswith("dernier_effdt")


# ----------------------------------------------------------------- écarts justifiés
def test_statut_absence_jointure_motif(result):
    f = get(result, "7603160", "statusReasonCode")
    assert f.verdict == JUSTIFIE and f.valeur_attendue == "170"
    assert f.preuves["jointure_motif"]["CodeStatutSystèmeExterne (Remphor)"] == "170"


def test_mojibake_justifie(result):
    f = get(result, "7603160", "detailedStatus")
    assert f.verdict == JUSTIFIE and f.regle_id == "R-NORMALISATION"


def test_anonymisation_courriel_et_libelle(result):
    assert all(f.verdict == JUSTIFIE for f in result.findings if f.champ_b in ("contactEmail", "positionName"))


def test_heures_par_defaut_du_poste(result):
    f = get(result, "3712987", "weeklyHoursOverride")
    assert f.verdict == JUSTIFIE and f.signature == "hours:defaut_poste_source_vide"


def test_type_contrat_derive(result):
    f = get(result, "1545850", "contractTypeCode")
    assert f.verdict == JUSTIFIE and f.valeur_attendue == "JWN"


# ----------------------------------------------------------------- conformes
def test_conformes(result):
    f = get(result, "8142123", "onboardDate")
    assert f.verdict == CONFORME and f.niveau.startswith("1")
    assert get(result, "2173396", "assignmentStartDate").verdict == CONFORME  # changement d'unité 320→352


def test_secondaires_appariees(result):
    sec = [f for f in result.findings if f.matricule == "7683990" and f.champ_b == "isPrimaryAssignment"]
    assert len(sec) == 3 and all(f.verdict != ANOMALIE for f in sec)


# ----------------------------------------------------------------- traçabilité et intégrité
def test_tout_verdict_est_explique(result):
    for f in result.findings:
        assert f.verdict in (CONFORME, JUSTIFIE, ANOMALIE)
        assert f.justification and f.regle_id and f.niveau and f.decide_par


def test_couverture_mapping_complete(result):
    assert not [r for r in result.meta["couverture_mapping"] if r["statut"] == "NON COUVERT"]


def test_sources_inchangees(result):
    assert all(i["intact"] for i in check_integrity(DEFAULT_DATA_DIR))


def test_priorites_ordonnees(result):
    anomalies = [f for f in result.findings if f.verdict == ANOMALIE]
    assert anomalies[0].priorite >= anomalies[-1].priorite > 0
