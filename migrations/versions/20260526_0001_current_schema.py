"""Create current Watchful Owl schema.

Revision ID: 20260526_0001
Revises:
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260526_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "signals" not in tables:
        _create_signals_table()
    else:
        _ensure_signal_columns(inspector)

    if "collection_runs" not in tables:
        _create_collection_runs_table()


def downgrade() -> None:
    op.drop_table("collection_runs")


def _create_signals_table() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("cves", sa.String(), nullable=False),
        sa.Column("keywords", sa.String(), nullable=False),
        sa.Column("products", sa.String(), nullable=False),
        sa.Column("github_links", sa.String(), nullable=False),
        sa.Column("github_stars", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_signal_indexes()


def _create_signal_indexes() -> None:
    for column in [
        "source",
        "source_type",
        "url",
        "published_at",
        "collected_at",
        "github_stars",
        "score",
        "confidence",
        "severity",
        "status",
        "is_favorite",
        "deleted_at",
    ]:
        op.create_index(f"ix_signals_{column}", "signals", [column])
    op.create_index("ix_signals_fingerprint", "signals", ["fingerprint"], unique=True)


def _ensure_signal_columns(inspector: sa.Inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns("signals")}
    if "is_favorite" not in columns:
        op.add_column(
            "signals",
            sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index("ix_signals_is_favorite", "signals", ["is_favorite"])
    if "deleted_at" not in columns:
        op.add_column("signals", sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.create_index("ix_signals_deleted_at", "signals", ["deleted_at"])


def _create_collection_runs_table() -> None:
    op.create_table(
        "collection_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("collected_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in [
        "source",
        "started_at",
        "finished_at",
        "duration_ms",
        "success",
        "collected_count",
    ]:
        op.create_index(f"ix_collection_runs_{column}", "collection_runs", [column])
