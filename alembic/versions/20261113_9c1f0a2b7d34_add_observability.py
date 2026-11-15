"""add observability traces

Revision ID: 9c1f0a2b7d34
Revises: d501556059a8
Create Date: 2026-11-13 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c1f0a2b7d34"
down_revision: str | Sequence[str] | None = "d501556059a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "traces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("intent", sa.String(length=30), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_traces_organization_id", "traces", ["organization_id"])
    op.create_index("ix_traces_conversation_id", "traces", ["conversation_id"])
    op.create_index(
        "ix_traces_organization_id_started_at",
        "traces",
        ["organization_id", "started_at"],
    )
    op.create_index(
        "ix_traces_conversation_id_started_at",
        "traces",
        ["conversation_id", "started_at"],
    )

    op.create_table(
        "spans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("parent_span_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_span_id"],
            ["spans.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index(
        "ix_spans_trace_id_started_at",
        "spans",
        ["trace_id", "started_at"],
    )
    op.create_index(
        "ix_spans_organization_id_started_at",
        "spans",
        ["organization_id", "started_at"],
    )

    op.create_table(
        "model_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("call_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "estimated_cost_usd",
            sa.Numeric(precision=18, scale=8),
            nullable=True,
        ),
        sa.Column("price_version", sa.String(length=40), nullable=True),
        sa.Column("service_tier", sa.String(length=30), nullable=True),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_calls_trace_id", "model_calls", ["trace_id"])
    op.create_index(
        "ix_model_calls_organization_id_created_at",
        "model_calls",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_model_calls_provider_model_created_at",
        "model_calls",
        ["provider", "model", "created_at"],
    )

    op.add_column("messages", sa.Column("trace_id", sa.Uuid(), nullable=True))
    op.create_index("ix_messages_trace_id", "messages", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_trace_id", table_name="messages")
    op.drop_column("messages", "trace_id")
    op.drop_index(
        "ix_model_calls_provider_model_created_at",
        table_name="model_calls",
    )
    op.drop_index(
        "ix_model_calls_organization_id_created_at",
        table_name="model_calls",
    )
    op.drop_index("ix_model_calls_trace_id", table_name="model_calls")
    op.drop_table("model_calls")
    op.drop_index(
        "ix_spans_organization_id_started_at",
        table_name="spans",
    )
    op.drop_index("ix_spans_trace_id_started_at", table_name="spans")
    op.drop_index("ix_spans_trace_id", table_name="spans")
    op.drop_table("spans")
    op.drop_index(
        "ix_traces_conversation_id_started_at",
        table_name="traces",
    )
    op.drop_index(
        "ix_traces_organization_id_started_at",
        table_name="traces",
    )
    op.drop_index("ix_traces_conversation_id", table_name="traces")
    op.drop_index("ix_traces_organization_id", table_name="traces")
    op.drop_table("traces")
