"""users_created_at_not_null

Revision ID: a1b2c3d4e5f6
Revises: e8f3a2b1c4d5
Create Date: 2026-06-15 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e8f3a2b1c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 users.created_at 回填为非空并与 ORM 模型对齐。"""
    op.execute(
        sa.text(
            """
            UPDATE users
            SET created_at = COALESCE(created_at, updated_at, now())
            WHERE created_at IS NULL
            """
        )
    )
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )


def downgrade() -> None:
    """恢复 users.created_at 为可空列。"""
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )
