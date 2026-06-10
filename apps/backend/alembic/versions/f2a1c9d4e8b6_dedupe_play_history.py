"""dedupe play history

Revision ID: f2a1c9d4e8b6
Revises: c85a4f26c4ef
Create Date: 2026-06-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f2a1c9d4e8b6"
down_revision: Union[str, Sequence[str], None] = "c85a4f26c4ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DELETE FROM play_history
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id, music_id
                        ORDER BY played_at DESC, id DESC
                    ) AS row_num
                FROM play_history
            ) ranked
            WHERE ranked.row_num > 1
        )
        """
    )
    op.execute(
        """
        DELETE FROM play_history
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id
                        ORDER BY played_at DESC, id DESC
                    ) AS row_num
                FROM play_history
            ) ranked
            WHERE ranked.row_num > 100
        )
        """
    )
    op.create_index(
        "uq_play_history_user_music",
        "play_history",
        ["user_id", "music_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_play_history_user_music", table_name="play_history")
