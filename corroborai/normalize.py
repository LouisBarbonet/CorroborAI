"""Normalisation des valeurs : vides, dates (sériel Excel / ISO / datetime), booléens,
nombres, encodage (mojibake), accents et zéros de tête.

Toutes les fonctions sont pures : elles ne modifient jamais les données d'origine.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from typing import Any

from ftfy import fix_text

EXCEL_EPOCH = dt.date(1899, 12, 30)
_NULL_TOKENS = {"", "none", "nan", "nat", "null", "-", "n/a"}
_TRUE = {"true", "oui", "o", "1", "y", "yes", "vrai"}
_FALSE = {"false", "non", "n", "0", "no", "faux"}


def is_null(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip().lower() in _NULL_TOKENS:
        return True
    try:  # pandas NaT / NA
        import pandas as pd

        if v is pd.NaT or (not isinstance(v, (str, bytes)) and pd.isna(v)):
            return True
    except (TypeError, ValueError):
        pass
    return False


def raw_str(v: Any) -> str | None:
    """Représentation brute lisible (utilisée pour la comparaison de niveau 1)."""
    if is_null(v):
        return None
    if isinstance(v, dt.datetime):
        return v.date().isoformat() if v.time() == dt.time(0) else v.isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def text(v: Any) -> str | None:
    """Texte normalisé : vide → None, espaces, réparation d'encodage (Ã¨ → è)."""
    if is_null(v):
        return None
    s = raw_str(v)
    fixed = fix_text(s)
    return re.sub(r"\s+", " ", fixed).strip()


def has_mojibake(v: Any) -> bool:
    if is_null(v) or not isinstance(v, str):
        return False
    return fix_text(v) != v


def strip_accents(s: str | None) -> str | None:
    if s is None:
        return None
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def to_date(v: Any) -> dt.date | None:
    """Accepte : datetime/date, sériel Excel (int/float/'34739'), ISO ('1995-02-09T00:00:00.000Z')."""
    if is_null(v):
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if hasattr(v, "to_pydatetime"):
        return v.to_pydatetime().date()
    if isinstance(v, (int, float)):
        return EXCEL_EPOCH + dt.timedelta(days=int(v))
    s = str(v).strip()
    if re.fullmatch(r"\d{4,6}(\.0+)?", s):
        return EXCEL_EPOCH + dt.timedelta(days=int(float(s)))
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return dt.date(int(m[3]), int(m[2]), int(m[1]))
    raise ValueError(f"Date non reconnue : {v!r}")


def to_bool(v: Any) -> bool | None:
    if is_null(v):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return None


def to_num(v: Any) -> float | None:
    if is_null(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return None


def code(v: Any) -> str | None:
    """Code numérique/alphanumérique sans zéros de tête ni décimales parasites ('00397' → '397', '40.0' → '40')."""
    if is_null(v):
        return None
    s = raw_str(v)
    if re.fullmatch(r"-?\d+(\.0+)?", s):
        return str(int(float(s)))
    return s.strip().upper()


def fmt(v: Any) -> str | None:
    """Mise en forme d'une valeur normalisée pour l'affichage/rapport."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:g}"
    return str(v)


def email(v: Any) -> str | None:
    t = text(v)
    return t.lower() if t else None


NORMALIZERS = {"text": text, "date": to_date, "bool": to_bool, "num": to_num, "code": code, "email": email}


def normalize(v: Any, kind: str) -> Any:
    return NORMALIZERS[kind](v)
