"""fix_moderation_version_defaults

Revision ID: c2718712b3e0
Revises: 037245d380e7
Create Date: 2026-06-26 21:30:07.687834

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2718712b3e0"
down_revision: Union[str, Sequence[str], None] = "037245d380e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # moderation_version 默认值必须 >= 1（满足 content_moderation_tasks 的 CHECK 约束）
    op.execute(
        "ALTER TABLE playlists ALTER COLUMN moderation_version SET DEFAULT 1"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN profile_moderation_version SET DEFAULT 1"
    )
    # 修正已有行的 0 值
    op.execute(
        "UPDATE playlists SET moderation_version = 1 WHERE moderation_version = 0"
    )
    op.execute(
        "UPDATE users SET profile_moderation_version = 1 WHERE profile_moderation_version = 0"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE playlists ALTER COLUMN moderation_version SET DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN profile_moderation_version SET DEFAULT 0"
    )
