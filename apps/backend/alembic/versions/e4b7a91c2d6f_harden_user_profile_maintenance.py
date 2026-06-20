"""harden user profile maintenance

Revision ID: e4b7a91c2d6f
Revises: 9a3232de3d59
Create Date: 2026-06-20 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4b7a91c2d6f"
down_revision: Union[str, Sequence[str], None] = "9a3232de3d59"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the per-conversation evaluation cursor and remove a duplicate index."""
    op.add_column(
        "ai_conversations",
        sa.Column(
            "profile_evaluated_human_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "chk_ai_conversations_profile_evaluated_count",
        "ai_conversations",
        "profile_evaluated_human_count >= 0",
    )
    op.drop_index("idx_user_profiles_user_id", table_name="user_profiles")


def downgrade() -> None:
    """Restore the previous schema."""
    op.create_index(
        "idx_user_profiles_user_id",
        "user_profiles",
        ["user_id"],
        unique=True,
    )
    op.drop_constraint(
        "chk_ai_conversations_profile_evaluated_count",
        "ai_conversations",
        type_="check",
    )
    op.drop_column("ai_conversations", "profile_evaluated_human_count")
