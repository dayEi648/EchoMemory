"""通知（Notification）相关的 ORM 模型定义模块。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    SmallInteger,
    String,
    desc,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.user import User


class Notification(Base):
    """系统通知模型，记录平台对用户产生的事件级提醒。

    target_type 取值：``user``（被关注通知，target_id 为关注者）、
    ``comment``（评论被点赞 / 被回复，target_id 为被作用的评论 id）、
    ``space_post``（空间动态被点赞 / 被评论，target_id 为动态 id）。
    extra 用于冗余展示所需的上下文（例如评论内容预览、动态内容预览），避免前端 N+1 拉取。
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "type >= 0 AND type <= 5", name="chk_notifications_type"
        ),
        CheckConstraint(
            "target_type IN ('user', 'comment', 'space_post')",
            name="chk_notifications_target_type",
        ),
        CheckConstraint(
            "actor_id IS NULL OR actor_id <> recipient_id",
            name="chk_notifications_no_self",
        ),
        Index(
            "idx_notifications_recipient_time",
            "recipient_id",
            desc("created_at"),
        ),
        Index(
            "idx_notifications_recipient_unread",
            "recipient_id",
            postgresql_where=text("is_read = false"),
        ),
        Index(
            "uq_notifications_dedupe_unread_with_actor",
            "recipient_id",
            "actor_id",
            "type",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("is_read = false AND actor_id IS NOT NULL"),
        ),
        Index(
            "uq_notifications_dedupe_unread_system",
            "recipient_id",
            "type",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("is_read = false AND actor_id IS NULL"),
        ),
    )

    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])
    actor: Mapped["User | None"] = relationship("User", foreign_keys=[actor_id])
