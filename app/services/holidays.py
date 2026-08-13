"""Italian public holidays + the Messina patron feast, for highlighting
festività on the roster and its exports (req: "Sundays + festività in red").

Sundays are handled by callers (``date.weekday() == 6``); this module returns
only the named public/patron holidays. The Messina patron feast — Madonna della
Lettera, 3 June — is included because the client operates in Messina.
"""

from datetime import date, timedelta


def _easter_sunday(year: int) -> date:
    """Gregorian Easter Sunday (Meeus/Jones/Butcher algorithm)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


# Fixed-date Italian public holidays (+ Messina patron feast on 3 June).
_FIXED: dict[tuple[int, int], str] = {
    (1, 1): "Capodanno",
    (1, 6): "Epifania",
    (4, 25): "Festa della Liberazione",
    (5, 1): "Festa dei Lavoratori",
    (6, 2): "Festa della Repubblica",
    (6, 3): "Madonna della Lettera (Messina)",
    (8, 15): "Ferragosto",
    (11, 1): "Ognissanti",
    (12, 8): "Immacolata Concezione",
    (12, 25): "Natale",
    (12, 26): "Santo Stefano",
}


def holiday_name(d: date) -> str | None:
    """The festività name for a date, or None. Movable feasts (Pasqua and
    Lunedì dell'Angelo) are derived from Easter each year."""
    fixed = _FIXED.get((d.month, d.day))
    if fixed:
        return fixed
    easter = _easter_sunday(d.year)
    if d == easter:
        return "Pasqua"
    if d == easter + timedelta(days=1):
        return "Lunedì dell'Angelo"
    return None
