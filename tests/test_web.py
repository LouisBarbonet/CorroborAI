"""Tests de la version web : routeur relais (Pyodide), instantané, sérialisation, API du chat."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from corroborai import serialize
from corroborai.ai.feedback import FeedbackStore
from corroborai.ai.llm.base import LLMError
from corroborai.ai.llm.relay import RecordingRouter, RelayRouter, canonical_key
from corroborai.chat_context import build_context, citable_refs
from corroborai.engine import Engine
from corroborai.models import ANOMALIE, JUSTIFIE
from tests.test_ai import EchoProvider, make_router


def test_instantane_rejoue_sans_appel(tmp_path):
    rec = RecordingRouter(make_router(EchoProvider()))
    res1 = Engine(router=rec, feedback=FeedbackStore(tmp_path / "a.json")).run()
    assert len(rec.recorded) == 3  # 2 champs ambigus (heures, lots de 25) + synthèse

    calls = []
    relay = RelayRouter("https://relais.test", rec.recorded, post=lambda url, p: calls.append(url) or {})
    res2 = Engine(router=relay, feedback=FeedbackStore(tmp_path / "b.json")).run()
    assert calls == []
    assert res2.counts() == res1.counts()
    assert res2.meta["synthese"]["fournisseur"] == "simule/echo"
    f = next(f for f in res2.findings if f.champ_b == "weeklyHoursOverride" and f.niveau.startswith("3"))
    assert "simule/echo" in f.decide_par


def test_relais_en_echec_repli_local(tmp_path):
    def boom(url, payload):
        raise LLMError("Le quota quotidien du relais est atteint.")

    relay = RelayRouter("https://relais.test", {}, post=boom)
    res = Engine(router=relay, feedback=FeedbackStore(tmp_path / "f.json")).run()
    assert res.meta["llm"]["utilise"] == ["gabarit-local"]
    assert res.counts()[ANOMALIE] == 57
    assert "quota" in relay.status()["fournisseurs"][0]["detail"]


def test_relais_envoie_uniquement_des_donnees_structurees(tmp_path):
    sent = []

    def fake(url, payload):
        sent.append((url, payload))
        if url.endswith("/judge"):
            return {"cas": [{"id": c["id"], "verdict": c["analyse_locale"]["verdict"], "confiance": 0.9,
                             "justification": "ok"} for c in payload["cas"]], "modele": "gemini-test", "cached": False}
        return {"resume": "Synthèse.", "causes_racines": [], "modele": "gemini-test", "cached": False}

    Engine(router=RelayRouter("https://relais.test", {}, post=fake), feedback=FeedbackStore(tmp_path / "f.json")).run()
    judge = [p for u, p in sent if u.endswith("/judge")]
    assert judge and all(set(p) == {"champ", "cas"} and len(p["cas"]) <= 25 for p in judge)
    keys = {"id", "valeur_systeme_A", "valeur_attendue_selon_regle", "valeur_systeme_B", "analyse_locale"}
    assert all(set(c) == keys for p in judge for c in p["cas"])  # aucune consigne ni texte libre envoyé


def test_cle_canonique_stable():
    assert canonical_key("judge", {"b": 1, "a": [1, 2]}) == canonical_key("judge", {"a": [1, 2], "b": 1})
    assert canonical_key("judge", {"a": 1}) != canonical_key("summary", {"a": 1})


def test_serialisation_et_contexte(tmp_path):
    res = Engine(use_llm=False, feedback=FeedbackStore(tmp_path / "f.json")).run()
    payload = json.loads(serialize.dumps(serialize.to_payload(res)))
    assert payload["summary"]["compteurs"]["total"] == 551 and len(payload["findings"]) == 551
    ctx = build_context(res)
    assert "[2762457/contractTypeCode]" in ctx and "[R-CONTRACT]" in ctx
    assert "[7603160/statusReasonCode]" in ctx  # détail des jointures Motif
    assert "[2762457/contractTypeCode]" in citable_refs(res)


def test_api_health_et_chat(monkeypatch):
    from api import main

    monkeypatch.setattr(main.LLMRouter, "chat", lambda self, msgs, ctx: {
        "reponse": "Voir [R-CONTRACT] et [Inventé].", "fournisseur": "test", "cached": False})
    client = TestClient(main.app)
    assert client.get("/api/health").json()["backend"] == "python"
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Pourquoi ?"}]})
    assert r.status_code == 200 and r.json()["reponse"] == "Voir [R-CONTRACT] et Inventé."
    assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "x" * 801}]}).status_code == 422
    assert client.post("/api/chat", json={"messages": [{"role": "assistant", "content": "x"}]}).status_code == 400


def test_verdict_justifie_reste_justifie_via_relais(tmp_path):
    relay = RelayRouter("", {})  # aucun relais : gabarit
    res = Engine(router=relay, feedback=FeedbackStore(tmp_path / "f.json")).run()
    f = next(f for f in res.findings if f.matricule == "3712987" and f.champ_b == "weeklyHoursOverride")
    assert f.verdict == JUSTIFIE  # heures par défaut du poste : justifié même sans LLM
