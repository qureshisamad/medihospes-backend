"""Reporting & export endpoints (v2).

Replaces the v1 attendance/discrepancy report. v2.0 employees receive the
schedule as exported files (req v2.0 §1.7, §4 "Export First"):
  * GET /reports/roster.xlsx  — monthly roster grid as Excel
  * GET /reports/roster.pdf   — monthly roster grid as PDF
  * GET /reports/overtime     — JSON hours/overtime summary (for screen)

No email/SMS, no payroll integration (req v2.0 §1.7).
"""

import calendar
import io
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_edit
from app.core.database import get_db
from app.models.employee import Employee
from app.models.roster import RosterAssignment
from app.models.shift_type import ShiftType
from app.models.user import User
from app.services.hours_service import employee_hours_summary, month_bounds

router = APIRouter(prefix="/reports", tags=["Reports & Export"])


def _build_grid(db: Session, year: int, month: int, department_id: int | None):
    """Return (employees, days, cell_map) where cell_map[(emp_id, day)] = label."""
    start, end = month_bounds(year, month)
    days = list(range(1, calendar.monthrange(year, month)[1] + 1))

    eq = db.query(Employee).filter(Employee.is_active.is_(True))
    if department_id is not None:
        eq = eq.filter(Employee.department_id == department_id)
    employees = eq.order_by(Employee.last_name, Employee.first_name).all()

    shift_codes = {s.id: s.code for s in db.query(ShiftType).all()}

    cells = (
        db.query(RosterAssignment)
        .filter(
            RosterAssignment.work_date >= start,
            RosterAssignment.work_date <= end,
        )
        .all()
    )
    cell_map: dict[tuple[int, int], str] = {}
    for c in cells:
        if c.shift_type_id:
            label = shift_codes.get(c.shift_type_id, "?")
        elif c.absence_code:
            label = c.absence_code.value
        else:
            label = ""
        cell_map[(c.employee_id, c.work_date.day)] = label
    return employees, days, cell_map


@router.get("/overtime")
def overtime_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    q = db.query(Employee).filter(Employee.is_active.is_(True))
    if department_id is not None:
        q = q.filter(Employee.department_id == department_id)
    return [
        employee_hours_summary(db, e, year, month)
        for e in q.order_by(Employee.last_name).all()
    ]


@router.get("/roster.xlsx")
def export_roster_xlsx(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    employees, days, cell_map = _build_grid(db, year, month, department_id)

    wb = Workbook()
    ws = wb.active
    ws.title = f"{calendar.month_abbr[month]} {year}"

    header_fill = PatternFill("solid", fgColor="1A7340")
    header_font = Font(bold=True, color="FFFFFF")
    centre = Alignment(horizontal="center")

    ws.cell(row=1, column=1, value="Employee").font = header_font
    ws.cell(row=1, column=1).fill = header_fill
    for i, d in enumerate(days, start=2):
        c = ws.cell(row=1, column=i, value=d)
        c.font = header_font
        c.fill = header_fill
        c.alignment = centre
        ws.column_dimensions[c.column_letter].width = 4

    for r, emp in enumerate(employees, start=2):
        ws.cell(row=r, column=1, value=f"{emp.last_name} {emp.first_name}")
        for i, d in enumerate(days, start=2):
            ws.cell(
                row=r, column=i, value=cell_map.get((emp.id, d), "")
            ).alignment = centre
    ws.column_dimensions["A"].width = 28

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"roster_{year}_{month:02d}.xlsx"
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/roster.pdf")
def export_roster_pdf(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    department_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _u: User = Depends(require_edit),
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    employees, days, cell_map = _build_grid(db, year, month, department_id)

    header = ["Employee"] + [str(d) for d in days]
    rows = [header]
    for emp in employees:
        rows.append(
            [f"{emp.last_name} {emp.first_name}"]
            + [cell_map.get((emp.id, d), "") for d in days]
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A7340")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    doc.build([table])
    buf.seek(0)
    fname = f"roster_{year}_{month:02d}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
