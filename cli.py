"""CorroborIA — exécution en ligne de commande.

Exemples :
    python cli.py                         # fichiers fournis, rapport dans ./output
    python cli.py --no-llm                # IA locale uniquement (aucun appel externe)
    python cli.py --source A.xlsx --destination B.xlsx --out rapports/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from corroborai.engine import Engine
from corroborai.models import ANOMALIE
from corroborai.report import export


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Corroboration intelligente Système A (RH) ↔ Système B (Temps)")
    ap.add_argument("--data-dir", type=Path, help="dossier contenant les 5 fichiers (défaut : corroborai-participants)")
    for k in ("source", "destination", "detail", "motif", "mapping"):
        ap.add_argument(f"--{k}", type=Path, help=f"chemin du fichier « {k} »")
    ap.add_argument("--out", type=Path, default=Path("output"), help="dossier de sortie des rapports")
    ap.add_argument("--no-llm", action="store_true", help="désactive les LLM (analyse IA locale uniquement)")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    paths = {k: getattr(args, k) for k in ("source", "destination", "detail", "motif", "mapping") if getattr(args, k)}
    res = Engine(use_llm=not args.no_llm).run(paths, args.data_dir)
    files = export(res, args.out)

    c = res.counts()
    print(f"\nCorroboration terminée en {res.meta['duree_s']} s")
    print(f"  Constats : {c['total']}  |  Anomalies : {c[ANOMALIE]}  |  Écarts justifiés : {c['Écart justifié']}  |"
          f"  Conformes : {c['Conforme']}  |  À valider : {c['a_valider']}")
    print(f"  IA utilisée : {', '.join(res.meta['llm']['utilise']) or '—'}")
    intact = all(i["intact"] for i in res.meta["integrite"])
    print(f"  Intégrité des fichiers sources : {'OK (inchangés)' if intact else 'ÉCART !'}")
    print("\nAnomalies (par priorité) :")
    for f in [f for f in res.findings if f.verdict == ANOMALIE]:
        flag = " [à valider]" if f.a_valider else ""
        print(f"  [{f.priorite:3d}] {f.matricule} {f.type_affectation or ''} {f.champ_b:<22} "
              f"attendu={f.valeur_attendue!s:<14} reçu={f.valeur_b!s:<14}{flag}")
    print(f"\nSynthèse : {res.meta['synthese'].get('resume')}")
    print("\nRapports :")
    for k, p in files.items():
        print(f"  {k:<14} {p.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
