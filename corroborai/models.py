from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CONFORME = "Conforme"
JUSTIFIE = "Écart justifié"
ANOMALIE = "Anomalie"
VERDICTS = (CONFORME, JUSTIFIE, ANOMALIE)

LEVEL_COMPARE = "1 - Comparaison brute"
LEVEL_RULE = "2 - Règle métier"
LEVEL_AI = "3 - Analyse IA"
LEVEL_EXPERT = "Expert"


@dataclass
class Expectation:
    """Valeur attendue dans le système cible après application d'une règle."""

    expected: Any
    explanation: str
    evidence: dict = field(default_factory=dict)
    covered: bool = True  # False : la règle ne couvre pas ce cas → analyse IA
    transformed: bool = False  # True : la valeur attendue résulte d'une transformation/jointure


@dataclass
class Finding:
    id: str
    matricule: str
    employe: str
    code_poste: str | None
    code_emploi: str | None
    type_affectation: str | None
    description: str
    champ_a: str
    champ_b: str
    valeur_a: str | None
    valeur_b: str | None
    valeur_attendue: str | None
    verdict: str
    niveau: str
    regle_id: str
    regle_texte: str
    decide_par: str
    justification: str
    confiance: float = 1.0
    priorite: int = 0
    a_valider: bool = False
    diagnostic: str = ""
    preuves: dict = field(default_factory=dict)
    ia: dict = field(default_factory=dict)
    criticite: float = 0.5
    signature: str = ""  # motif généralisable (utilisé par la boucle de rétroaction expert)

    def to_dict(self) -> dict:
        return asdict(self)
