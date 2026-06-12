"""私信会话（Conversation）、消息（DirectMessage）与用户屏蔽（UserBlock）相关的 ORM 模型定义。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.user import User


class Conversation(Base):
    """两个用户之间的私信会话元数据模型。

    存储约定：``user1_id < user2_id``，由 CHECK 约束保证；查询时通过
    (min(a, b), max(a, b)) 归一化定位会话，使每对用户至多对应一条记录。
    ``user1_unread_count`` / ``user2_unread_count`` 反规范化各方未读数；
    ``last_message_id`` 反规范化最后一条消息的主键，用于会话列表降序排序与预览。
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user1_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user2_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    last_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey(
            "direct_messages.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_conversations_last_message_id",
        ),
    )
    user1_unread_count: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    user2_unread_count: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "user1_id < user2_id", name="chk_conversations_user_order"
        ),
        CheckConstraint(
            "user1_unread_count >= 0", name="chk_conversations_user1_unread_nonneg"
        ),
        CheckConstraint(
            "user2_unread_count >= 0", name="chk_conversations_user2_unread_nonneg"
        ),
        UniqueConstraint(
            "user1_id", "user2_id", name="uq_conversations_user_pair"
        ),
        Index("idx_conversations_user1_time", "user1_id", desc("updated_at")),
        Index("idx_conversations_user2_time", "user2_id", desc("updated_at")),
    )

    user1: Mapped["User"] = relationship("User", foreign_keys=[user1_id])
    user2: Mapped["User"] = relationship("User", foreign_keys=[user2_id])
    last_message: Mapped["DirectMessage | None"] = relationship(
        "DirectMessage",
        foreign_keys=[last_message_id],
        post_update=True,
    )
    messages: Mapped[list["DirectMessage"]] = relationship(
        "DirectMessage",
        back_populates="conversation",
        foreign_keys="DirectMessage.conversation_id",
    )


class DirectMessage(Base):
    """私信单条消息模型。"""

    __tablename__ = "direct_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "idx_direct_messages_conversation_time",
            "conversation_id",
            desc("created_at"),
        ),
        Index("idx_direct_messages_sender", "sender_id"),
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
        foreign_keys=[conversation_id],
    )
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])


class UserBlock(Base):
    """用户屏蔽关系模型。被屏蔽方无法再向 blocker 发送私信。"""

    __tablename__ = "user_blocks"

    blocker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "blocker_id <> blocked_id", name="chk_user_blocks_no_self"
        ),
        Index("idx_user_blocks_blocked", "blocked_id"),
    )

    blocker: Mapped["User"] = relationship("User", foreign_keys=[blocker_id])
    blocked: Mapped["User"] = relationship("User", foreign_keys=[blocked_id])
