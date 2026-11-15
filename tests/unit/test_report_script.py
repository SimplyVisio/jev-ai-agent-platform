"""Pruebas de los helpers puros del reporte de terminal."""

import importlib.util
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace
from zoneinfo import ZoneInfo

import pytest


def _load_script() -> ModuleType:
    """Carga ``scripts/report.py`` sin convertirlo en un paquete instalado."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "report.py"
    spec = importlib.util.spec_from_file_location("jev_report_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = _load_script()


def test_table_handles_no_rows() -> None:
    """Las secciones vacías no deben romper el cálculo de anchos."""
    assert report._table(("a", "bb"), []).splitlines() == ["a  bb", "-  --"]


def test_table_aligns_columns() -> None:
    rendered = report._table(("name", "value"), [("uno", 1), ("dos", None)])
    assert rendered.splitlines() == [
        "name  value",
        "----  -----",
        "uno   1    ",
        "dos   —    ",
    ]


def test_period_requires_ordered_dates() -> None:
    args = SimpleNamespace(
        date_from=date(2026, 10, 2),
        date_to=date(2026, 10, 1),
    )
    with pytest.raises(SystemExit, match="posterior"):
        report._period(args)


def test_period_defaults_to_last_seven_utc_days() -> None:
    # No congelamos el reloj: comprobamos la relación entre extremos.
    args = SimpleNamespace(date_from=None, date_to=None)
    date_from, date_to = report._period(args)
    assert (date_to - date_from).days == 6
    assert date_from <= datetime.now(ZoneInfo("UTC")).date()


def test_cost_cell_distinguishes_unknown_from_zero() -> None:
    assert report._cost_cell(None, 0) == "—"
    assert report._cost_cell(None, 2) == "— (2 sin precio)"
    assert report._cost_cell(Decimal("0"), 0) == "$0.00000000"
    assert report._cost_cell(Decimal("0.1"), 1) == "$0.10000000 (+1 sin precio)"
