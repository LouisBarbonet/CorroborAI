"""Tests de la couche IA : chaîne de repli LLM, fusion des avis, boucle de rétroaction expert."""
from __future__ import annotations

import pytest

from corroborai.ai.feedback import FeedbackStore
from corroborai.ai.llm.base import LLMError, Provider, parse_json
from corroborai.ai.llm.router import LLMRouter
from corroborai.engine import Engine
from corroborai.models import ANOMALIE, JUSTIFIE


class FailingProvider(Provider):
    name, model = "en-panne", "x"

    def available(self):
        return True, "ok"

    def complete_json(self, system, user, schema):
        raise LLMError("délai dépassé")


class EchoProvider(Provider):
    """Fournisseur simulé : confirme l'analyse locale (comme un LLM d'accord)."""
    name, model = "simule", "echo"

    def __init__(self):
        self.calls = 0

    def available(self):
        return True, "ok"

    def complete_json(self, system, user, schema):
        import json
        self.calls += 1
        data = json.loads(user)
        if "cas" not in data:
            return {"resume": "Synthèse simulée.", "causes_racines": []}
        return {"cas": [{"id": c["id"], "verdict": c["analyse_locale"]["verdict"], "confiance": 0.9,
                         "justification": "Avis simulé."} for c in data["cas"]]}


def make_router(*providers):
    r = LLMRouter(order="template")
    r.providers = [*providers, r.providers[-1]]
    import tempfile
    from pathlib import Path
    r.cache.dir = Path(tempfile.mkdtemp())
    return r


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "0")


def test_parse_json_tolerant():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Voici : {"a": {"b": 2}} fin') == {"a": {"b": 2}}


def test_repli_vers_fournisseur_suivant():
    echo = EchoProvider()
    r = make_router(FailingProvider(), echo)
    cases = [{"id": "c1", "analyse_locale": {"verdict": JUSTIFIE, "confiance": 0.8, "signaux": [], "justification": "x"}}]
    out, used = r.judge("champ", "règle", cases)
    assert used == "simule/echo" and out["c1"]["verdict"] == JUSTIFIE
    assert any("échec" in t["statut"] for t in r.trace)


def test_repli_final_gabarit_sans_aucun_llm(tmp_path):
    r = make_router(FailingProvider())
    res = Engine(router=r, feedback=FeedbackStore(tmp_path / "f.json")).run()
    assert res.meta["llm"]["utilise"] == ["gabarit-local"]
    assert res.counts()[ANOMALIE] >= 10


def test_llm_confirme_et_trace(tmp_path):
    echo = EchoProvider()
    res = Engine(router=make_router(echo), feedback=FeedbackStore(tmp_path / "f.json")).run()
    f = next(f for f in res.findings if f.champ_b == "contactEmail")
    assert "LLM (simule/echo)" in f.decide_par and f.ia["llm"]["verdict"] == JUSTIFIE
    assert echo.calls >= 4  # appels groupés par champ (pas un appel par ligne)


def test_desaccord_llm_signale_a_valider(tmp_path):
    class Contrarian(EchoProvider):
        def complete_json(self, system, user, schema):
            out = super().complete_json(system, user, schema)
            for c in out.get("cas", []):
                c["verdict"] = ANOMALIE if c["verdict"] == JUSTIFIE else JUSTIFIE
                c["confiance"] = 0.55
            return out

    res = Engine(router=make_router(Contrarian()), feedback=FeedbackStore(tmp_path / "f.json")).run()
    f = next(f for f in res.findings if f.champ_b == "positionName")
    assert f.verdict == JUSTIFIE and f.a_valider and f.ia.get("desaccord")


def test_correction_expert_par_motif(tmp_path):
    store = FeedbackStore(tmp_path / "f.json")
    eng = Engine(router=make_router(), feedback=store, use_llm=False)
    res = eng.run()
    f = next(f for f in res.findings if f.signature == "hours:override_non_transmis")
    store.add(f, JUSTIFIE, "Horaire réduit géré par l'override de l'horaire type.", portee="motif", auteur="test")
    res2 = eng.run()
    impacted = [x for x in res2.findings if x.signature == "hours:override_non_transmis"]
    assert len(impacted) == 6 and all(x.verdict == JUSTIFIE and x.niveau == "Expert" for x in impacted)
    assert res2.meta["ml"]["corrections_expert"] == 6
