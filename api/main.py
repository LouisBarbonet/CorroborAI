"""API FastAPI + service de l'interface web (build Vite dans dist/).

Lancement :  npm run build  puis  uvicorn api.main:app   →  http://127.0.0.1:8000
Développement de l'interface :  npm run dev  (Vite, proxy /api → 127.0.0.1:8000)
"""
from __future__ import annotations

import re
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from corroborai import serialize
from corroborai.ai.feedback import FeedbackStore
from corroborai.ai.llm import LLMRouter
from corroborai.ai.llm.base import LLMError
from corroborai.chat_context import build_context, citable_refs
from corroborai.engine import Engine, Result
from corroborai.models import VERDICTS
from corroborai.report import build_csv, build_excel

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

app = FastAPI(title="CorroborIA", version="1.1.0", description="Corroboration intelligente Système A (RH) ↔ Système B (Temps)")
_state: dict = {"result": None, "paths": None, "use_llm": True, "context": None}
_lock = threading.Lock()
feedback = FeedbackStore()


def _run(paths=None, use_llm: bool = True) -> Result:
    with _lock:
        res = Engine(router=LLMRouter(), feedback=feedback, use_llm=use_llm).run(paths)
        _state.update(result=res, paths=paths, use_llm=use_llm, context=None)
        return res


def _result() -> Result:
    return _state["result"] or _run()


@app.get("/api/health")
def health():
    return {"ok": True, "backend": "python"}


@app.post("/api/run")
async def run(use_llm: bool = True, source: UploadFile | None = File(None), destination: UploadFile | None = File(None),
              detail: UploadFile | None = File(None), motif: UploadFile | None = File(None),
              mapping: UploadFile | None = File(None)):
    """Lance la corroboration. Fichiers facultatifs : sinon les extractions fournies sont utilisées.
    Les fichiers téléversés sont copiés dans un dossier temporaire ; les originaux ne sont jamais modifiés."""
    uploads = {"source": source, "destination": destination, "detail": detail, "motif": motif, "mapping": mapping}
    paths = None
    if any(u and u.filename for u in uploads.values()):
        tmp = Path(tempfile.mkdtemp(prefix="corroboria_"))
        paths = {}
        for k, u in uploads.items():
            if u and u.filename:
                p = tmp / f"{k}_{Path(u.filename).name}"
                with open(p, "wb") as fh:
                    shutil.copyfileobj(u.file, fh)
                paths[k] = p
    try:
        res = _run(paths, use_llm)
    except (FileNotFoundError, KeyError, ValueError) as e:
        raise HTTPException(400, f"Fichiers invalides : {e}") from e
    return serialize.summary(res)


@app.get("/api/summary")
def summary():
    return serialize.summary(_result())


@app.get("/api/findings")
def findings(verdict: str | None = None, champ: str | None = None, q: str | None = None, a_valider: bool | None = None,
             niveau: str | None = None):
    out = []
    for f in _result().findings:
        if verdict and f.verdict != verdict:
            continue
        if champ and f.champ_b != champ:
            continue
        if a_valider is not None and f.a_valider != a_valider:
            continue
        if niveau and not f.niveau.startswith(niveau):
            continue
        if q and q.lower() not in f"{f.matricule} {f.employe} {f.champ_b} {f.valeur_a} {f.valeur_b} {f.justification}".lower():
            continue
        out.append(serialize.finding_row(f))
    return out


@app.get("/api/findings/{fid:path}")
def finding(fid: str):
    f = _result().by_id(fid)
    if not f:
        raise HTTPException(404, "Constat introuvable")
    return f.to_dict()


class FeedbackIn(BaseModel):
    finding_id: str
    verdict: str
    commentaire: str = ""
    portee: str = "cas"
    auteur: str = "expert"


@app.post("/api/feedback")
def post_feedback(fb: FeedbackIn):
    f = _result().by_id(fb.finding_id)
    if not f:
        raise HTTPException(404, "Constat introuvable")
    if fb.verdict not in VERDICTS:
        raise HTTPException(400, f"Verdict invalide (valeurs : {', '.join(VERDICTS)})")
    try:
        entry = feedback.add(f, fb.verdict, fb.commentaire, fb.portee, fb.auteur)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    res = _run(_state["paths"], _state["use_llm"])  # ré-exécution : la règle apprise s'applique immédiatement
    touched = [x.id for x in res.findings if x.niveau == "Expert"]
    return {"correction": entry, "constats_impactes": touched, "compteurs": res.counts()}


@app.get("/api/feedback")
def list_feedback():
    return feedback.load()


@app.delete("/api/feedback")
def clear_feedback():
    feedback.clear()
    _run(_state["paths"], _state["use_llm"])
    return {"ok": True}


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=800)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=8)


@app.post("/api/chat")
def chat(body: ChatIn):
    """Chat du jury (même consigne que le relais Cloudflare). Réponses identiques servies depuis .cache/llm/."""
    if body.messages[-1].role != "user":
        raise HTTPException(400, "Le dernier message doit être une question.")
    res = _result()
    if _state["context"] is None:
        _state["context"] = build_context(res)
    try:
        out = LLMRouter().chat([m.model_dump() for m in body.messages], _state["context"])
    except LLMError as e:
        raise HTTPException(503, str(e)) from e
    # Repères inventés par le modèle : crochets retirés (même traitement que le relais Cloudflare)
    reperes = citable_refs(res)
    out["reponse"] = re.sub(r"\[([^\[\]\n]{1,80})\]", lambda m: m.group(0) if m.group(0) in reperes else m.group(1), out["reponse"])
    return out


@app.get("/api/llm-status")
def llm_status():
    return LLMRouter().status()


@app.get("/api/export.xlsx")
def export_xlsx():
    return Response(build_excel(_result()), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="rapport_corroboration.xlsx"'})


@app.get("/api/export.csv")
def export_csv(verdict: str | None = None):
    return Response(build_csv(_result(), verdict), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="rapport_corroboration.csv"'})


@app.get("/")
def index():
    if (DIST / "index.html").exists():
        return FileResponse(DIST / "index.html")
    return HTMLResponse("<h1>Interface non construite</h1><p>Lancez <code>npm install</code> puis <code>npm run build</code>, "
                        "ou utilisez <code>npm run dev</code>. L'API est disponible sous <a href='/docs'>/docs</a>.</p>")


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST), name="static")
