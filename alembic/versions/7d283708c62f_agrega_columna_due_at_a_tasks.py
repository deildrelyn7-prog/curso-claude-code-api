"""agrega columna due_at a tasks

Revision ID: 7d283708c62f
Revises: 323ce5858585
Create Date: 2026-09-07 19:25:10.929916

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7d283708c62f'
down_revision: str | Sequence[str] | None = '323ce5858585'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tasks",
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tasks", "due_at")
