"""Appariement des lignes Système A ↔ Système B.

Un employé peut avoir plusieurs affectations (primaire, temporaire, secondaires). La cible ne
contient pas le numéro de poste : la clé est donc (Matricule, CodeEmploi, type d'affectation),
avec repli sur (Matricule, CodeEmploi) puis (Matricule) pour signaler les incohérences de type.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import normalize as N


@dataclass
class Pair:
    src: dict | None
    dst: dict | None
    methode: str  # « clé complète », « repli emploi », « manquant cible », « surplus cible »
    src_index: int | None = None
    dst_index: int | None = None


def src_type(row: dict) -> str | None:
    return N.code(row.get("TypeAffectation"))


def dst_type(row: dict) -> str:
    p, t = N.to_bool(row.get("isPrimaryAssignment")), N.to_bool(row.get("isTemporaryAssignment"))
    return "P" if p else ("A" if t else "S")


def match(source: pd.DataFrame, destination: pd.DataFrame) -> list[Pair]:
    src = source.to_dict("records")
    dst = destination.to_dict("records")
    used: set[int] = set()
    pairs: dict[int, Pair] = {}

    def keys_src(r, level):
        base = (N.code(r.get("Matricule")), N.code(r.get("CodeEmploi")), src_type(r))
        return base[:3 - level]

    def keys_dst(r, level):
        base = (N.code(r.get("personId")), N.code(r.get("positionId")), dst_type(r))
        return base[:3 - level]

    labels = {0: "clé complète (matricule + emploi + type)", 1: "repli (matricule + emploi)"}
    for level in (0, 1):
        for i, s in enumerate(src):
            if i in pairs:
                continue
            k = keys_src(s, level)
            cand = [j for j, d in enumerate(dst) if j not in used and keys_dst(d, level) == k]
            if cand:
                used.add(cand[0])
                pairs[i] = Pair(s, dst[cand[0]], labels[level], i, cand[0])
    out = [pairs.get(i) or Pair(s, None, "manquant dans le Système B", i, None) for i, s in enumerate(src)]
    out += [Pair(None, d, "surplus dans le Système B", None, j) for j, d in enumerate(dst) if j not in used]
    return out
