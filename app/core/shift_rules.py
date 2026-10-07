"""Special-employee shift restrictions ("Dipendenti Speciali").

Some employees can only work certain shifts — e.g. an educator who only does
mornings, or a gap-filler. This module keeps that logic DYNAMIC and SCALABLE:

* No employee is hard-coded anywhere — the constraint lives on
  ``Employee.shift_restriction`` (a plain string), so any employee can be given
  one and new restriction types are added here in one place.
* What counts as "morning"/"afternoon"/"night" is DERIVED from each shift
  type's own times, so it adapts automatically if shifts are edited or added.

Current restriction types:
  * ``morning_only`` — may only be assigned/substituted onto morning shifts.

To add another (e.g. ``afternoon_only``), add it to ``RESTRICTION_ALLOWED``
and, if it should block manual assignment, to ``RESTRICTION_BLOCK_MSG``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import cycle; only needed for typing
    from app.models.shift_type import ShiftType

# Restriction key -> set of day-parts the employee may work.
RESTRICTION_ALLOWED: dict[str, set[str]] = {
    "morning_only": {"morning"},
}

# Restriction key -> English message shown when a manual assignment is blocked.
# The text IS the i18n lookup key (see app/core/i18n.py), so it gets localized
# by the HTTP exception handler.
RESTRICTION_BLOCK_MSG: dict[str, str] = {
    "morning_only": "This employee can only be assigned morning shifts.",
}

# Valid values accepted from the API (besides None).
VALID_RESTRICTIONS: set[str] = set(RESTRICTION_ALLOWED)


def shift_day_part(st: "ShiftType | None") -> str:
    """Classify a shift by time of day from its own start time / flags.

    Returns one of: ``rest`` (zero-duration, e.g. R), ``night`` (crosses
    midnight or starts late-evening / pre-dawn, e.g. N(a), N(B), the Smontante
    "coming-off-night" marker), ``morning`` (starts in the AM, e.g. M/Ed), or
    ``afternoon`` (everything else, e.g. P/N/Ed). Derived, never hard-coded.
    """
    if st is None:
        return "rest"
    if (st.duration_hours or 0) <= 0:
        return "rest"
    if st.crosses_midnight:
        return "night"
    start = st.start_time
    hour = start.hour if start is not None else 0
    if hour >= 20 or hour < 5:
        return "night"
    if hour < 12:
        return "morning"
    return "afternoon"


def shift_allowed_for(restriction: str | None, st: "ShiftType | None") -> bool:
    """True if an employee with ``restriction`` may work shift ``st``.

    No restriction → always allowed. Rest days are never blocked (not a worked
    shift). An unknown restriction value fails open (allowed) so a bad value
    never silently hides every shift.
    """
    if not restriction:
        return True
    allowed = RESTRICTION_ALLOWED.get(restriction)
    if allowed is None:
        return True
    part = shift_day_part(st)
    if part == "rest":
        return True
    return part in allowed


def block_message(restriction: str | None) -> str | None:
    """English block message for a restriction, or None if it doesn't block."""
    if not restriction:
        return None
    return RESTRICTION_BLOCK_MSG.get(restriction)
