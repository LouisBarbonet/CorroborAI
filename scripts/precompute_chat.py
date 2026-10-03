"""Pré-calcule les réponses du chat pour les questions d'exemple (filet de sécurité du site public).

    python scripts/precompute_chat.py        (ou : npm run precompute)

Lit data/chat-questions.json, interroge le LLM configuré (.env) avec exactement le contexte embarqué dans le
relais (worker/src/data.generated.json) et écrit data/precomputed/chat.json. Les réponses déjà obtenues sont
servies par le cache disque .cache/llm/ : on peut relancer après un quota atteint sans repayer.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from corroborai.ai.llm import LLMRouter  # noqa: E402
from corroborai.ai.llm.base import LLMError  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    questions = json.loads((ROOT / "data" / "chat-questions.json").read_text(encoding="utf-8"))
    context = json.loads((ROOT / "worker" / "src" / "data.generated.json").read_text(encoding="utf-8"))["context"]
    out_path = ROOT / "data" / "precomputed" / "chat.json"
    previous = {}
    if out_path.exists():
        previous = {a["question"]: a for a in json.loads(out_path.read_text(encoding="utf-8")).get("reponses", [])}
    router = LLMRouter()
    answers, failures = [], 0
    for q in questions:
        try:
            r = router.chat([{"role": "user", "content": q}], context)
            answers.append({"question": q, "reponse": r["reponse"], "fournisseur": r["fournisseur"]})
            print(f"✓ {'(cache) ' if r['cached'] else ''}{q}")
        except LLMError as e:
            failures += 1
            if q in previous:
                answers.append(previous[q])
            print(f"✗ {q} — {e}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"genere_le": dt.datetime.now().isoformat(timespec="seconds"), "reponses": answers},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(answers)}/{len(questions)} réponses écrites dans {out_path.relative_to(ROOT)}"
          + (f" ({failures} échec(s) : relancez plus tard, le cache évite de repayer)" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
