"""add user level trigger

Revision ID: 6d7bd218983c
Revises: f2a1c9d4e8b6
Create Date: 2026-06-11 04:48:37.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6d7bd218983c"
down_revision: Union[str, Sequence[str], None] = "f2a1c9d4e8b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建触发器函数与触发器，使 users.level 随 exp 变更自动计算。"""
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_update_user_level()
        RETURNS TRIGGER AS $$
        BEGIN
            SELECT COALESCE(MAX(level), 0) INTO NEW.level
            FROM level_config
            WHERE min_exp <= NEW.exp;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_level_on_exp_change
        BEFORE INSERT OR UPDATE OF exp ON users
        FOR EACH ROW
        EXECUTE FUNCTION fn_update_user_level();
        """
    )


def downgrade() -> None:
    """删除触发器与触发器函数。"""
    op.execute(
        "DROP TRIGGER IF EXISTS trg_users_level_on_exp_change ON users;"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS fn_update_user_level();"
    )
