"""Chargement en lecture seule des extractions + vérification d'intégrité (sha256 du manifest)."""
from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "corroborai-participants"

DEFAULT_FILES = {
    "source": "Employe_Source_Anonymise_VF.xlsx",
    "destination": "Employe_Destination_Anonymise_VF.xlsx",
    "detail": "détail_du_poste.xlsx",
    "motif": "Motif de la situation d'emploi.xlsx",
    "mapping": "Mapping.xlsx",
}

DETAIL_COLUMNS = [
    "IdentifiantPoste", "IdentifiantEmploi", "CodeDirectionAffectée", "DateEffetAffectation",
    "CodeBudget", "IndicateurGestion", "CodePosteSecondaire", "MatriculeGestionnaire",
    "HeuresSemaineContrat", "HeuresJourContrat", "JoursTravailléesSemaine",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Datasets:
    source: pd.DataFrame
    destination: pd.DataFrame
    detail: pd.DataFrame
    motif: pd.DataFrame
    mapping: pd.DataFrame
    situation_rules: pd.DataFrame
    paths: dict[str, Path] = field(default_factory=dict)
    integrity: list[dict] = field(default_factory=list)


def _read_excel(path: Path, **kw) -> pd.DataFrame:
    # dtype=object : on conserve les types natifs (datetime, int, float, str) pour la normalisation.
    with open(path, "rb") as f:  # ouverture en lecture seule explicite
        return pd.read_excel(io.BytesIO(f.read()), dtype=object, **kw)


def read_detail(path: Path) -> pd.DataFrame:
    """Le fichier « détail du poste » contient un CSV tassé dans une seule colonne Excel."""
    df = _read_excel(path, header=None)
    if df.shape[1] >= len(DETAIL_COLUMNS) and df.iloc[1:, 1:].notna().any().any():
        df.columns = df.iloc[0]
        return df.iloc[1:].reset_index(drop=True)
    lines = [str(v) for v in df.iloc[:, 0].tolist() if pd.notna(v)]
    header = [h.strip() for h in lines[0].split(",")]
    rows = [[c.strip() or None for c in ln.split(",")] for ln in lines[1:]]
    return pd.DataFrame(rows, columns=header, dtype=object)


def read_mapping(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retourne (mapping champ à champ avec règles fusionnées, tableau des règles de situation d'emploi)."""
    raw = _read_excel(path, sheet_name=None, header=None)
    sheet = raw[next(iter(raw))]
    records, current = [], None
    for idx in range(1, len(sheet)):
        desc, a, b, rule = (sheet.iat[idx, i] if i < sheet.shape[1] else None for i in range(4))
        clean = lambda v: None if pd.isna(v) else str(v).strip()
        desc, a, b, rule = map(clean, (desc, a, b, rule))
        if b:  # nouvelle ligne de mapping (champ cible présent)
            current = {"description": desc or (current or {}).get("description"), "champ_a": a,
                       "champ_b": b, "regle": rule or "", "champs_a_complementaires": [],
                       "ligne_excel": idx + 1}
            records.append(current)
        elif current is not None:  # ligne de continuation (règle ou champ source complémentaire)
            if a:
                current["champs_a_complementaires"].append(a)
            if rule:
                current["regle"] = (current["regle"] + "\n" + rule).strip()
    mapping = pd.DataFrame(records)
    situ_name = next((n for n in raw if "situation" in n.lower()), None)
    situ = pd.DataFrame()
    if situ_name:
        s = raw[situ_name]
        situ = pd.DataFrame(s.iloc[1:].values, columns=[str(c) for c in s.iloc[0]])
    return mapping, situ


def check_integrity(data_dir: Path) -> list[dict]:
    manifest = data_dir / "manifest.json"
    if not manifest.exists():
        return []
    out = []
    for f in json.loads(manifest.read_text(encoding="utf-8")).get("files", []):
        p = data_dir / f["path"]
        actual = sha256(p) if p.exists() else None
        out.append({"fichier": f["path"], "sha256_attendu": f["sha256"], "sha256_actuel": actual,
                    "intact": actual == f["sha256"]})
    return out


def load(paths: dict[str, Path] | None = None, data_dir: Path | None = None) -> Datasets:
    data_dir = Path(data_dir or DEFAULT_DATA_DIR)
    resolved = {k: data_dir / v for k, v in DEFAULT_FILES.items()}
    resolved.update({k: Path(v) for k, v in (paths or {}).items() if v})
    for k, p in resolved.items():
        if not p.exists():
            raise FileNotFoundError(f"Fichier « {k} » introuvable : {p}")
    mapping, situ = read_mapping(resolved["mapping"])
    return Datasets(
        source=_read_excel(resolved["source"]),
        destination=_read_excel(resolved["destination"]),
        detail=read_detail(resolved["detail"]),
        motif=_read_excel(resolved["motif"]),
        mapping=mapping,
        situation_rules=situ,
        paths=resolved,
        integrity=check_integrity(data_dir),
    )
