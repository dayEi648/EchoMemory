"""add_play_history_music_time_index

Revision ID: 45a5683e8a03
Revises: b4e8c2a1f903
Create Date: 2026-06-12 21:44:26.998632

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45a5683e8a03'
down_revision: Union[str, Sequence[str], None] = 'b4e8c2a1f903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'idx_play_history_music_time',
        'play_history',
        ['music_id', sa.literal_column('played_at DESC')],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_play_history_music_time', table_name='play_history')
