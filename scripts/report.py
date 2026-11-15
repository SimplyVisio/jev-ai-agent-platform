"""Reporte de observabilidad, costes y analítica en la terminal.

Uso:
    docker compose run --rm backend python scripts/report.py --organization Demo
    docker compose run --rm backend python scripts/report.py --organization Demo \
        --date-from 2026-10-01 --date-to 2026-10-31
    docker compose run --rm backend python scripts/report.py --trace <trace_id>
"""

import argparse
import asyncio
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jev_ai.config import get_settings
from jev_ai.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)
from jev_ai.modules.analytics import service as analytics
from jev_ai.modules.organizations.models import Organization
from jev_ai.observability.models import ModelCall, Span, Trace


def _table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """Dibuja una tabla simple sin dependencias externas."""
    rows = [tuple("—" if value is None else str(value) for value in row) for row in rows]
    widths = [
        max([len(str(header)), *(len(row[index]) for row in rows)])
        for index, header in enumerate(headers)
    ]
    lines = [
        "  ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in rows
    )
    return "\n".join(lines)


def _cost(value: Decimal | None) -> str:
    """Formatea un coste estimado con precisión suficiente para verlo."""
    if value is None:
        return "—"
    return f"${value:.8f}"


def _cost_cell(total: Decimal | None, unpriced: int) -> str:
    """Distingue coste desconocido de coste cero y avisa de llamadas sin tarifa."""
    if total is None:
        return "—" if unpriced == 0 else f"— ({unpriced} sin precio)"
    suffix = f" (+{unpriced} sin precio)" if unpriced else ""
    return f"{_cost(total)}{suffix}"


def _trace_cost(calls: Sequence[ModelCall]) -> str:
    """Suma solo los costes conocidos de las llamadas de una traza."""
    priced = [call.estimated_cost_usd for call in calls if call.estimated_cost_usd is not None]
    if not priced:
        return _cost_cell(None, len(calls))
    return _cost_cell(sum(priced, Decimal("0")), len(calls) - len(priced))


def _money(value: Decimal) -> str:
    """Formatea importes de negocio con dos decimales."""
    return f"{value:.2f}"


def _period(args: argparse.Namespace) -> tuple[date, date]:
    """Calcula un rango inclusivo; por defecto, los últimos siete días."""
    date_to = args.date_to or datetime.now(UTC).date()
    date_from = args.date_from or date_to - timedelta(days=6)
    if date_from > date_to:
        raise SystemExit("--date-from no puede ser posterior a --date-to")
    return date_from, date_to


def _start(date_value: date) -> datetime:
    """Inicio UTC inclusivo de un día."""
    return datetime.combine(date_value, time.min, tzinfo=UTC)


def _end(date_value: date) -> datetime:
    """Inicio UTC exclusivo del día siguiente."""
    return datetime.combine(date_value + timedelta(days=1), time.min, tzinfo=UTC)


async def _organization(session: AsyncSession, name: str | None) -> Organization | None:
    """Resuelve una organización por nombre sin asumir que sea única."""
    if name is None:
        return None
    organization = await session.scalar(
        select(Organization).where(Organization.name == name).order_by(Organization.created_at)
    )
    if organization is None:
        raise SystemExit(f"No existe la organización {name!r}")
    return organization


def _trace_filters(
    query: Any,
    *,
    organization_id: UUID | None,
    date_from: date,
    date_to: date,
) -> Any:
    """Aplica organización y rango temporal a una consulta de trazas."""
    query = query.where(
        Trace.started_at >= _start(date_from),
        Trace.started_at < _end(date_to),
    )
    if organization_id is not None:
        query = query.where(Trace.organization_id == organization_id)
    return query


def _model_call_filters(
    query: Any,
    *,
    organization_id: UUID | None,
    date_from: date,
    date_to: date,
) -> Any:
    """Aplica organización y rango temporal a una consulta de llamadas."""
    query = query.where(
        ModelCall.created_at >= _start(date_from),
        ModelCall.created_at < _end(date_to),
    )
    if organization_id is not None:
        query = query.where(ModelCall.organization_id == organization_id)
    return query


async def _summary(
    session: AsyncSession,
    *,
    organization_id: UUID | None,
    date_from: date,
    date_to: date,
) -> tuple[int, int, int, float | None, int, Decimal | None, int]:
    """Devuelve trazas, estados, duración media, coste conocido y llamadas sin tarifa."""
    trace_row = (
        await session.execute(
            _trace_filters(
                select(
                    func.count(Trace.id),
                    func.count(Trace.id).filter(Trace.status == "ok"),
                    func.count(Trace.id).filter(Trace.status == "error"),
                    func.avg(Trace.duration_ms),
                ),
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            )
        )
    ).one()
    call_row = (
        await session.execute(
            _model_call_filters(
                select(
                    func.count(ModelCall.id),
                    func.count(ModelCall.estimated_cost_usd),
                    func.coalesce(func.sum(ModelCall.estimated_cost_usd), 0),
                ),
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            )
        )
    ).one()
    return (
        int(trace_row[0]),
        int(trace_row[1]),
        int(trace_row[2]),
        None if trace_row[3] is None else float(trace_row[3]),
        int(call_row[0]),
        Decimal(call_row[2]) if call_row[1] else None,
        int(call_row[0]) - int(call_row[1]),
    )


async def _cost_rows(
    session: AsyncSession,
    *,
    organization_id: UUID | None,
    date_from: date,
    date_to: date,
) -> list[tuple[str, str, str, int, int, int, int, Decimal]]:
    """Agrupa llamadas y coste por proveedor, modelo y tipo."""
    query = _model_call_filters(
        select(
            ModelCall.provider,
            ModelCall.model,
            ModelCall.call_type,
            func.count(ModelCall.id),
            func.coalesce(func.sum(ModelCall.input_tokens), 0),
            func.coalesce(func.sum(ModelCall.output_tokens), 0),
            func.count(ModelCall.estimated_cost_usd),
            func.coalesce(func.sum(ModelCall.estimated_cost_usd), 0),
        ),
        organization_id=organization_id,
        date_from=date_from,
        date_to=date_to,
    ).group_by(ModelCall.provider, ModelCall.model, ModelCall.call_type)
    query = query.order_by(func.coalesce(func.sum(ModelCall.estimated_cost_usd), 0).desc())
    rows = (await session.execute(query)).all()
    return [
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            int(row[3]),
            int(row[4]),
            int(row[5]),
            int(row[6]),
            Decimal(row[7]),
        )
        for row in rows
    ]


async def _latest_traces(
    session: AsyncSession,
    *,
    organization_id: UUID | None,
    date_from: date,
    date_to: date,
    limit: int,
) -> list[Trace]:
    """Lista las trazas más recientes del periodo."""
    query = (
        _trace_filters(
            select(Trace),
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
        )
        .order_by(Trace.started_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(query)).all())


async def _calls_for_traces(
    session: AsyncSession,
    trace_ids: Sequence[UUID],
) -> dict[UUID, list[ModelCall]]:
    """Carga las llamadas de las trazas mostradas."""
    if not trace_ids:
        return {}
    rows = list(
        (
            await session.scalars(
                select(ModelCall)
                .where(ModelCall.trace_id.in_(trace_ids))
                .order_by(ModelCall.created_at)
            )
        ).all()
    )
    grouped: dict[UUID, list[ModelCall]] = {}
    for row in rows:
        grouped.setdefault(row.trace_id, []).append(row)
    return grouped


async def _print_trace_detail(session: AsyncSession, trace_id: UUID) -> int:
    """Imprime spans y llamadas de una traza concreta."""
    trace = await session.get(Trace, trace_id)
    if trace is None:
        print(f"No existe la traza {trace_id}")
        return 1

    spans = list(
        (
            await session.scalars(
                select(Span).where(Span.trace_id == trace_id).order_by(Span.started_at)
            )
        ).all()
    )
    calls = list(
        (
            await session.scalars(
                select(ModelCall)
                .where(ModelCall.trace_id == trace_id)
                .order_by(ModelCall.created_at)
            )
        ).all()
    )
    print(f"Traza {trace.id}")
    print(
        f"  status={trace.status} intent={trace.intent or '—'} "
        f"duration_ms={trace.duration_ms if trace.duration_ms is not None else '—'} "
        f"org={trace.organization_id}"
    )
    print(f"  started_at={trace.started_at.isoformat()}")

    print("\nSpans:")
    print(
        _table(
            ("name", "kind", "status", "duration_ms", "detail"),
            [
                (
                    span.name,
                    span.kind,
                    span.status,
                    span.duration_ms,
                    None if span.attributes is None else span.attributes.get("detail"),
                )
                for span in spans
            ],
        )
    )

    print("\nModel calls:")
    print(
        _table(
            ("provider", "model", "type", "status", "in", "out", "latency_ms", "cost"),
            [
                (
                    call.provider,
                    call.model,
                    call.call_type,
                    call.status,
                    call.input_tokens,
                    call.output_tokens,
                    None if call.latency_ms is None else round(call.latency_ms, 2),
                    _cost(call.estimated_cost_usd),
                )
                for call in calls
            ],
        )
    )
    return 0


async def report(args: argparse.Namespace) -> int:
    """Ejecuta las consultas y renderiza el reporte."""
    engine = create_database_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            if args.trace is not None:
                return await _print_trace_detail(session, args.trace)

            organization = await _organization(session, args.organization)
            organization_id = None if organization is None else organization.id
            date_from, date_to = _period(args)
            total, ok, errors, avg_ms, calls_count, total_cost, unpriced = await _summary(
                session,
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            )
            costs = await _cost_rows(
                session,
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
            )
            traces = await _latest_traces(
                session,
                organization_id=organization_id,
                date_from=date_from,
                date_to=date_to,
                limit=args.limit,
            )
            calls_by_trace = await _calls_for_traces(session, [trace.id for trace in traces])

            label = organization.name if organization is not None else "todas las organizaciones"
            print("JEV AI — Reporte de observabilidad y analítica")
            print(f"Organización: {label}")
            print(f"Periodo: {date_from.isoformat()} → {date_to.isoformat()}")
            print("\nObservabilidad")
            print(
                _table(
                    ("trazas", "ok", "error", "duración media", "model calls", "coste estimado"),
                    [
                        (
                            total,
                            ok,
                            errors,
                            f"{avg_ms:.2f} ms" if avg_ms is not None else "—",
                            calls_count,
                            _cost_cell(total_cost, unpriced),
                        )
                    ],
                )
            )

            print("\nÚltimas trazas")
            if traces:
                print(
                    _table(
                        ("trace_id", "inicio", "status", "intent", "ms", "calls", "coste"),
                        [
                            (
                                trace.id,
                                trace.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                                trace.status,
                                trace.intent,
                                None if trace.duration_ms is None else round(trace.duration_ms, 2),
                                len(calls_by_trace.get(trace.id, [])),
                                _trace_cost(calls_by_trace.get(trace.id, [])),
                            )
                            for trace in traces
                        ],
                    )
                )
                print(
                    "\nDetalle de una traza: "
                    "docker compose run --rm backend python scripts/report.py --trace <trace_id>"
                )
            else:
                print("  Sin trazas en el periodo.")

            print("\nCostes por proveedor / modelo / tipo")
            if costs:
                print(
                    _table(
                        ("provider", "model", "tipo", "calls", "tokens in", "tokens out", "coste"),
                        [
                            (
                                provider,
                                model,
                                call_type,
                                count,
                                tokens_in,
                                tokens_out,
                                _cost_cell(cost if priced else None, count - priced),
                            )
                            for (
                                provider,
                                model,
                                call_type,
                                count,
                                tokens_in,
                                tokens_out,
                                priced,
                                cost,
                            ) in costs
                        ],
                    )
                )
            else:
                print("  Sin llamadas a modelos en el periodo.")

            if organization is not None:
                overview = await analytics.get_overview(
                    session,
                    organization.id,
                    date_from,
                    date_to,
                )
                campaigns = await analytics.list_campaign_performance(
                    session,
                    organization.id,
                    date_from,
                    date_to,
                    limit=5,
                    offset=0,
                )
                print("\nAnalítica")
                print(
                    _table(
                        ("métrica", "valor"),
                        [
                            ("impressions", overview.impressions),
                            ("clicks", overview.clicks),
                            ("landing_page_views", overview.landing_page_views),
                            ("spend", _money(overview.spend)),
                            ("leads", overview.leads),
                            ("sales", overview.sales),
                            ("revenue", _money(overview.revenue)),
                            ("ctr", overview.ctr),
                            ("cpc", overview.cpc),
                            ("roas", overview.roas),
                        ],
                    )
                )
                print("\nCampañas por gasto")
                if campaigns:
                    print(
                        _table(
                            ("campaña", "spend", "leads", "revenue", "roas"),
                            [
                                (
                                    campaign.campaign_name,
                                    _money(campaign.metrics.spend),
                                    campaign.metrics.leads,
                                    _money(campaign.metrics.revenue),
                                    campaign.metrics.roas,
                                )
                                for campaign in campaigns
                            ],
                        )
                    )
                else:
                    print("  Sin campañas con datos en el periodo.")
            else:
                print("\nAnalítica: usá --organization para incluir métricas de negocio.")
            return 0
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    """Define los filtros del reporte."""
    parser = argparse.ArgumentParser(description="Reporte de observabilidad y analítica.")
    parser.add_argument("--organization", default=None, help="Nombre de la organización.")
    parser.add_argument("--date-from", type=date.fromisoformat, default=None)
    parser.add_argument("--date-to", type=date.fromisoformat, default=None)
    parser.add_argument("--limit", type=int, default=10, help="Trazas recientes a mostrar.")
    parser.add_argument("--trace", type=UUID, default=None, help="Detalle de una traza.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(report(parse_args())))
