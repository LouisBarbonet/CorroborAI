"""Génère les données embarquées dans le site statique et dans le relais Cloudflare.

    python scripts/export_snapshot.py        (ou : npm run snapshot)

Produit :
- web/src/generated/snapshot.json   : résultat complet (résumé + constats) + réponses LLM enregistrées, affiché
                                      instantanément par le site et rejoué par le moteur Pyodide sans appel ;
- rapport/                           : rapport de corroboration (Excel + CSV) publié dans le dépôt ;
- worker/src/data.generated.json    : consignes (prompts/prompts.json), contexte du chat, textes des règles par
                                      champ et repères citables — le relais construit lui-même ses consignes.
Utilise le LLM configuré dans .env (Gemini) et le cache disque .cache/llm/ : relançable sans coût.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from corroborai import serialize  # noqa: E402
from corroborai.ai.feedback import FeedbackStore  # noqa: E402
from corroborai.ai.llm import LLMRouter  # noqa: E402
from corroborai.ai.llm.base import load_prompts  # noqa: E402
from corroborai.ai.llm.relay import RecordingRouter  # noqa: E402
from corroborai.chat_context import build_context, citable_refs  # noqa: E402
from corroborai.engine import Engine  # noqa: E402
from corroborai.mapping import FIELD_SPECS, rule_text  # noqa: E402
from corroborai.rules import build_refdata  # noqa: E402
from corroborai.io_loader import load  # noqa: E402
from corroborai.report import export  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    router = RecordingRouter(LLMRouter())
    fb = FeedbackStore(Path(tempfile.mkdtemp()) / "feedback.json")  # instantané sans correction expert
    res = Engine(router=router, feedback=fb).run()
    used = res.meta["llm"]["utilise"]
    if not used or any(u.startswith("gabarit") for u in used):
        print(f"⚠ Aucun LLM réel utilisé ({used}). Configurez GEMINI_API_KEY dans .env pour un instantané complet.")

    payload = serialize.to_payload(res)
    payload["recorded"] = router.recorded
    out_web = ROOT / "web" / "src" / "generated" / "snapshot.json"
    out_web.parent.mkdir(parents=True, exist_ok=True)
    out_web.write_text(serialize.dumps(payload), encoding="utf-8")

    ref = build_refdata(load())
    worker_data = {
        "prompts": load_prompts(),
        "context": build_context(res),
        "regles_par_champ": {s.champ_b: rule_text(s, ref.mapping_by_b) for s in FIELD_SPECS},
        "champs": [s.champ_b for s in FIELD_SPECS],
        "reperes": sorted(citable_refs(res)),
        "genere_le": res.meta["date_execution"],
    }
    out_worker = ROOT / "worker" / "src" / "data.generated.json"
    out_worker.parent.mkdir(parents=True, exist_ok=True)
    out_worker.write_text(json.dumps(worker_data, ensure_ascii=False, indent=1), encoding="utf-8")

    # Rapport de corroboration publié dans le dépôt (autorisé par Loto-Québec) : les juges n'ont rien à régénérer.
    files = export(res, ROOT / "rapport")

    c = res.counts()
    print(f"Instantané : {c} — LLM : {used} — {len(router.recorded)} réponse(s) enregistrée(s)")
    print(f"  rapport/ : {', '.join(p.name for p in files.values())}")
    print(f"  {out_web.relative_to(ROOT)} ({out_web.stat().st_size // 1024} Ko)")
    print(f"  {out_worker.relative_to(ROOT)} (contexte : {len(worker_data['context'])} caractères)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
