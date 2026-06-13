"""add_forward_count_to_music_album_playlist

Revision ID: 39c71a50067c
Revises: 45a5683e8a03
Create Date: 2026-06-12 22:50:55.386308

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '39c71a50067c'
down_revision: Union[str, Sequence[str], None] = '45a5683e8a03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为专辑、音乐、歌单添加转发次数字段及非负约束。"""
    op.add_column(
        'albums',
        sa.Column(
            'forward_count',
            sa.BigInteger(),
            server_default=sa.text('0'),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'chk_albums_forward_count_nonnegative',
        'albums',
        'forward_count >= 0',
    )
    op.add_column(
        'musics',
        sa.Column(
            'forward_count',
            sa.BigInteger(),
            server_default=sa.text('0'),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'chk_musics_forward_count_nonnegative',
        'musics',
        'forward_count >= 0',
    )
    op.add_column(
        'playlists',
        sa.Column(
            'forward_count',
            sa.BigInteger(),
            server_default=sa.text('0'),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'chk_playlists_forward_count_nonnegative',
        'playlists',
        'forward_count >= 0',
    )


def downgrade() -> None:
    """移除专辑、音乐、歌单的转发次数字段及非负约束。"""
    op.drop_constraint(
        'chk_playlists_forward_count_nonnegative',
        'playlists',
        type_='check',
    )
    op.drop_column('playlists', 'forward_count')
    op.drop_constraint(
        'chk_musics_forward_count_nonnegative',
        'musics',
        type_='check',
    )
    op.drop_column('musics', 'forward_count')
    op.drop_constraint(
        'chk_albums_forward_count_nonnegative',
        'albums',
        type_='check',
    )
    op.drop_column('albums', 'forward_count')
