"""Backend message localization (Accept-Language -> it / en).

Mirrors the frontend in-house i18n (``frontend/src/lib/i18n.tsx``). The default
locale is Italian to match the UI. The frontend sets ``Accept-Language`` to the
chosen locale ("it" / "en") on every request, so generated backend text —
auto-fill results, change-history detail, and API error details — comes back in
the user's language.

Three surfaces are localized:

* **HTTP error details** — translated centrally by an exception handler
  (``register_i18n_handlers``). The English string raised at the call site acts
  as the lookup key, so endpoints stay untouched. See ``translate_detail``.
* **Auto-fill results** — ``tr(key, locale, **vars)`` called inside
  ``rotation_service`` with the request locale threaded in.
* **Change-history detail** — stored structured (JSON ``{"k": key, ...vars}``)
  and rendered at READ time via ``render_log_detail`` so a language switch
  reflows the whole history. Legacy rows (plain strings) pass through unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Header

DEFAULT_LOCALE = "it"
SUPPORTED = ("it", "en")

# Calendar labels for exports (Excel / PDF). Months are 1-indexed via helpers
# below; weekday lists are indexed by date.weekday() (Monday = 0 … Sunday = 6).
_WEEKDAY_INITIALS = {
    "en": ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
    "it": ["Lu", "Ma", "Me", "Gi", "Ve", "Sa", "Do"],
}
_MONTH_NAMES = {
    "en": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
    "it": [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ],
}
_MONTH_ABBR = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "it": ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
           "Lug", "Ago", "Set", "Ott", "Nov", "Dic"],
}

# Codes, proper names and DB-sourced labels are intentionally NOT translated
# (shift codes M/P/N, absence codes B/C1, house & category names).

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # --- HTTP error details (key == the English text raised at call site) ---
        "Employee not found": "Employee not found",
        "Shift type not found": "Shift type not found",
        "Rotation pattern not found": "Rotation pattern not found",
        "Department code already exists": "Department code already exists",
        "Department not found": "Department not found",
        "Cannot delete a department with employees": "Cannot delete a department with employees",
        "Site code already exists": "Site code already exists",
        "Site not found": "Site not found",
        "Shift code already exists": "Shift code already exists",
        "Cycle must have at least one step": "Cycle must have at least one step",
        "Email already registered": "Email already registered",
        "User not found": "User not found",
        "Email already in use": "Email already in use",
        "Cannot deactivate yourself": "Cannot deactivate yourself",
        "Invalid credentials": "Invalid credentials",
        "Invalid or expired token": "Invalid or expired token",
        "User not found or inactive": "User not found or inactive",
        "Job title name already exists": "Job title name already exists",
        "Job title not found": "Job title not found",
        "Job title name already in use": "Job title name already in use",
        "This employee can only be assigned morning shifts.": "This employee can only be assigned morning shifts.",
        "Shift not allowed": "Shift not allowed for this employee.",
        "This employee cannot be scheduled at that site.": "This employee cannot be scheduled at that site.",
        # --- Auto-fill results ---
        "af.no_active": "No active employees in this category.",
        "af.pending_note": " ({count} pending)",
        "af.imbalance": (
            "Working staff{pending}: {working}, but the required total "
            "(M+P/N+S+R = {formula}) is {total}. Coverage will not balance — "
            "adjust the counts, the staff, or who is pending."
        ),
        "af.rest_gap": (
            "Order {a}→{b} leaves only {gap:.0f}h rest (min {min_rest:.0f}h) — "
            "check the shift sequence."
        ),
        "af.day1": "Day 1: {code} has {got}, expected {req}.",
        "af.unmet": "{date} {code}: {got} of {req} (short {short})",
        "af.identical": (
            "{count} employees share the same day-1 shift and will get "
            "identical schedules: {names}"
        ),
        # --- Change-history detail ---
        "log.manual_set.shift": "Set {code}",
        "log.manual_set.absence": "Set {code}",
        "log.manual_set.pending": "Set pending",
        "log.manual_set.note": "Set note",
        "log.manual_clear": "Cleared cell",
        "log.clear_month": "Cleared {count} cells for {ym}",
        "log.clear_month.scope": " ({scope})",
        "log.clear_month.absences_kept": " — absences kept",
        "log.auto_fill": "Auto-fill {name} {ym} — {cells} cells, {mode}",
        "log.auto_fill.mode_reset": "reset (manual edits cleared)",
        "log.auto_fill.mode_kept": "manual edits kept",
        "log.swap": "Swapped shifts with {name}",
        "log.cascade.one": "Cascaded {count} following day from {date}",
        "log.cascade.many": "Cascaded {count} following days from {date}",
        # --- Exports (Excel / PDF) ---
        "rep.employee": "Employee",
        "rep.pending": "Pend",
        "rep.title": "Monthly Roster — {month} {year}",
        "rep.days_range": "(days {start}–{end})",
        "rep.doc_title": "Roster {ym}",
        "rep.coverage": "Coverage",
        "rep.cov_legend": "Coverage: green = complete, orange = understaffed, red = overstaffed",
    },
    "it": {
        # --- HTTP error details ---
        "Employee not found": "Dipendente non trovato",
        "Shift type not found": "Tipo di turno non trovato",
        "Rotation pattern not found": "Schema di rotazione non trovato",
        "Department code already exists": "Codice reparto già esistente",
        "Department not found": "Reparto non trovato",
        "Cannot delete a department with employees": "Impossibile eliminare un reparto con dipendenti",
        "Site code already exists": "Codice sede già esistente",
        "Site not found": "Sede non trovata",
        "Shift code already exists": "Codice turno già esistente",
        "Cycle must have at least one step": "Il ciclo deve avere almeno un passo",
        "Email already registered": "Email già registrata",
        "User not found": "Utente non trovato",
        "Email already in use": "Email già in uso",
        "Cannot deactivate yourself": "Non puoi disattivare te stesso",
        "Invalid credentials": "Credenziali non valide",
        "Invalid or expired token": "Token non valido o scaduto",
        "User not found or inactive": "Utente non trovato o inattivo",
        "Job title name already exists": "Nome mansione già esistente",
        "Job title not found": "Mansione non trovata",
        "Job title name already in use": "Nome mansione già in uso",
        "This employee can only be assigned morning shifts.": "Questo dipendente può essere assegnato solo a turni del mattino.",
        "Shift not allowed": "Turno non consentito per questo dipendente.",
        "This employee cannot be scheduled at that site.": "Questo dipendente non può essere pianificato in quella sede.",
        # --- Auto-fill results ---
        "af.no_active": "Nessun dipendente attivo in questa categoria.",
        "af.pending_note": " ({count} in attesa)",
        "af.imbalance": (
            "Personale in servizio{pending}: {working}, ma il totale richiesto "
            "(M+P/N+S+R = {formula}) è {total}. La copertura non sarà bilanciata "
            "— modifica i numeri, il personale o chi è in attesa."
        ),
        "af.rest_gap": (
            "L'ordine {a}→{b} lascia solo {gap:.0f}h di riposo (min {min_rest:.0f}h) "
            "— controlla la sequenza dei turni."
        ),
        "af.day1": "Giorno 1: {code} ha {got}, previsti {req}.",
        "af.unmet": "{date} {code}: {got} di {req} (mancano {short})",
        "af.identical": (
            "{count} dipendenti hanno lo stesso turno del giorno 1 e avranno "
            "orari identici: {names}"
        ),
        # --- Change-history detail ---
        "log.manual_set.shift": "Turno {code} impostato",
        "log.manual_set.absence": "Assenza {code} impostata",
        "log.manual_set.pending": "Impostato in attesa",
        "log.manual_set.note": "Nota impostata",
        "log.manual_clear": "Cella svuotata",
        "log.clear_month": "{count} celle cancellate per {ym}",
        "log.clear_month.scope": " ({scope})",
        "log.clear_month.absences_kept": " — assenze mantenute",
        "log.auto_fill": "Compilazione automatica {name} {ym} — {cells} celle, {mode}",
        "log.auto_fill.mode_reset": "reset (modifiche manuali cancellate)",
        "log.auto_fill.mode_kept": "modifiche manuali mantenute",
        "log.swap": "Turni scambiati con {name}",
        "log.cascade.one": "Propagato su {count} giorno successivo dal {date}",
        "log.cascade.many": "Propagato su {count} giorni successivi dal {date}",
        # --- Exports (Excel / PDF) ---
        "rep.employee": "Dipendente",
        "rep.pending": "Att.",
        "rep.title": "Turni mensili — {month} {year}",
        "rep.days_range": "(giorni {start}–{end})",
        "rep.doc_title": "Turni {ym}",
        "rep.coverage": "Copertura",
        "rep.cov_legend": "Copertura: verde = completa, arancione = sotto organico, rosso = sopra organico",
    },
}


def resolve_locale(accept_language: str | None) -> str:
    """Pick a supported locale from an Accept-Language header value.

    The frontend sends a bare "it" / "en", but this also tolerates full
    header syntax ("it-IT,it;q=0.9,en;q=0.8") by matching the primary subtag
    of the first understood tag. Falls back to Italian.
    """
    if not accept_language:
        return DEFAULT_LOCALE
    for part in accept_language.split(","):
        tag = part.split(";")[0].strip().lower()
        if not tag:
            continue
        primary = tag.split("-")[0]
        if primary in SUPPORTED:
            return primary
    return DEFAULT_LOCALE


def tr(key: str, locale: str = DEFAULT_LOCALE, **kwargs: Any) -> str:
    """Translate ``key`` into ``locale`` and interpolate ``{vars}``.

    Falls back locale -> English -> the raw key. If interpolation fails
    (missing var), the uninterpolated template is returned rather than raising.
    """
    table = MESSAGES.get(locale) or MESSAGES[DEFAULT_LOCALE]
    template = table.get(key)
    if template is None:
        template = MESSAGES["en"].get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def weekday_initial(weekday: int, locale: str = DEFAULT_LOCALE) -> str:
    """Two-letter weekday label (date.weekday(): Monday = 0 … Sunday = 6)."""
    table = _WEEKDAY_INITIALS.get(locale) or _WEEKDAY_INITIALS[DEFAULT_LOCALE]
    return table[weekday]


def month_name(month: int, locale: str = DEFAULT_LOCALE) -> str:
    """Full month name (month is 1-indexed)."""
    table = _MONTH_NAMES.get(locale) or _MONTH_NAMES[DEFAULT_LOCALE]
    return table[month - 1]


def month_abbr(month: int, locale: str = DEFAULT_LOCALE) -> str:
    """Abbreviated month name (month is 1-indexed)."""
    table = _MONTH_ABBR.get(locale) or _MONTH_ABBR[DEFAULT_LOCALE]
    return table[month - 1]


def translate_detail(detail: Any, locale: str) -> Any:
    """Translate an HTTP error ``detail``. Non-string or unknown details
    (e.g. pydantic validation arrays, dynamic strings) pass through as-is."""
    if not isinstance(detail, str):
        return detail
    table = MESSAGES.get(locale) or MESSAGES[DEFAULT_LOCALE]
    return table.get(detail, detail)


def get_locale(
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
) -> str:
    """FastAPI dependency: the request's resolved locale ("it" / "en")."""
    return resolve_locale(accept_language)


def log_detail(key: str, **params: Any) -> str:
    """Serialize a change-log detail to translate later, at read time.

    Stored in ``RosterChangeLog.detail`` as JSON ``{"k": key, ...params}``.
    ``render_log_detail`` expands it in the reader's locale.
    """
    return json.dumps({"k": key, **params}, ensure_ascii=False)


def render_log_detail(raw: str | None, locale: str) -> str | None:
    """Expand a stored change-log detail into localized text.

    Legacy / plain-string rows (not our JSON envelope) are returned unchanged,
    so history written before this change still displays.
    """
    if not raw:
        return raw
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    if not isinstance(data, dict) or "k" not in data:
        return raw

    key = data["k"]

    # Plural / composite keys need a little logic beyond a flat lookup.
    if key == "log.cascade":
        count = data.get("count", 0)
        sub = "log.cascade.one" if count == 1 else "log.cascade.many"
        return tr(sub, locale, count=count, date=data.get("date", ""))

    if key == "log.auto_fill":
        mode_key = (
            "log.auto_fill.mode_reset"
            if data.get("reset")
            else "log.auto_fill.mode_kept"
        )
        mode = tr(mode_key, locale)
        return tr(
            "log.auto_fill",
            locale,
            name=data.get("name", ""),
            ym=data.get("ym", ""),
            cells=data.get("cells", 0),
            mode=mode,
        )

    if key == "log.clear_month":
        text = tr(
            "log.clear_month",
            locale,
            count=data.get("count", 0),
            ym=data.get("ym", ""),
        )
        scope = data.get("scope")
        if scope:
            text += tr("log.clear_month.scope", locale, scope=scope)
        if data.get("keep_absences"):
            text += tr("log.clear_month.absences_kept", locale)
        return text

    # Flat keys: pass remaining params straight through.
    params = {k: v for k, v in data.items() if k != "k"}
    return tr(key, locale, **params)


def register_i18n_handlers(app) -> None:
    """Install an exception handler that localizes HTTP error details.

    Wraps Starlette's default so status code and headers (e.g. the
    ``WWW-Authenticate`` on 401s) are preserved; only a string ``detail`` is
    translated, using the request's Accept-Language.
    """
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from starlette.responses import JSONResponse

    @app.exception_handler(StarletteHTTPException)
    async def _localized_http_exception_handler(request, exc):  # noqa: ANN001
        locale = resolve_locale(request.headers.get("accept-language"))
        detail = translate_detail(exc.detail, locale)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=getattr(exc, "headers", None),
        )
