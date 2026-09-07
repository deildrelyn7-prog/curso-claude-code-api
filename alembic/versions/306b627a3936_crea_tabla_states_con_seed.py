"""crea tabla states con seed

Revision ID: 306b627a3936
Revises: 7a7144ffd331
Create Date: 2026-09-04 22:54:42.266446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '306b627a3936'
down_revision: Union[str, Sequence[str], None] = '7a7144ffd331'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


states_table = sa.table(
    "states",
    sa.column("code", sa.String),
    sa.column("sort_order", sa.Integer),
)

CATALOG = [
    {"code": "PENDIENTE", "sort_order": 1},
    {"code": "EN_CURSO", "sort_order": 2},
    {"code": "BLOQUEADA", "sort_order": 3},
    {"code": "HECHA", "sort_order": 4},
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    insert_stmt = sa.dialects.postgresql.insert(states_table).values(CATALOG)
    insert_stmt = insert_stmt.on_conflict_do_nothing(index_elements=["code"])
    op.execute(insert_stmt)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("states")
