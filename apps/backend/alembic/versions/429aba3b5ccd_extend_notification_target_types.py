"""extend_notification_target_types

Revision ID: 429aba3b5ccd
Revises: c2718712b3e0
Create Date: 2026-06-26 21:56:14.383809

"""

from typing import Sequence, Union

from alembic import op

revision: str = "429aba3b5ccd"
down_revision: Union[str, Sequence[str], None] = "c2718712b3e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_TYPES = "'user', 'comment', 'space_post'"
_NEW_TYPES = "'user', 'comment', 'space_post', 'playlist', 'user_profile'"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS chk_notifications_target_type"
    )
    op.execute(
        f"ALTER TABLE notifications ADD CONSTRAINT chk_notifications_target_type "
        f"CHECK (target_type IN ({_NEW_TYPES})) NOT VALID"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS chk_notifications_target_type"
    )
    op.execute(
        f"ALTER TABLE notifications ADD CONSTRAINT chk_notifications_target_type "
        f"CHECK (target_type IN ({_OLD_TYPES})) NOT VALID"
    )
