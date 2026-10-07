"""Absence code short labels (shown in the roster grid & exports).

These are the Italian company abbreviations the manager wants IN the cell
(e.g. "Fe" for B / Ferie). Like shift codes they are NOT translated — they are
standard codes. Keep in sync with the frontend ABSENCE_SHORT map in
``frontend/src/lib/types.ts``.
"""

ABSENCE_SHORT: dict[str, str] = {
    "B": "Fe",    # Ferie
    "B1": "Mal",  # Malattia
    "B2": "TT",   # Trasferimento temporaneo
    "C1": "SF",   # Sostituzione fissa
    "C2": "SV",   # Sostituzione variabile
    "SOL": "SOL",  # Solidarietà (20H) — kept as-is
}


def absence_short(code: str) -> str:
    """Short cell label for an absence code; unknown codes pass through."""
    return ABSENCE_SHORT.get(code, code)
