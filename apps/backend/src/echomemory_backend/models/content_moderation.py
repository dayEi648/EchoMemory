"""内容审核任务、历史与用户统计模型。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from echomemory_backend.db.base import Base


class ContentModerationTask(Base):
    """可靠异步内容审核任务。"""

    __tablename__ = "content_moderation_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moderation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING", server_default="PENDING"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    agent_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "content_type IN ('comment', 'space_post', 'playlist', 'user_profile')",
            name="chk_content_moderation_tasks_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="chk_content_moderation_tasks_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts",
            name="chk_content_moderation_tasks_attempts",
        ),
        CheckConstraint(
            "moderation_version > 0",
            name="chk_content_moderation_tasks_version",
        ),
        UniqueConstraint(
            "content_type",
            "content_id",
            "moderation_version",
            name="uq_content_moderation_task_version",
        ),
        Index(
            "idx_content_moderation_tasks_claim",
            "status",
            "available_at",
            "id",
        ),
        Index(
            "idx_content_moderation_tasks_content",
            "content_type",
            "content_id",
        ),
    )


class ContentModerationHistory(Base):
    """每次有效 Agent 或人工审核结果。"""

    __tablename__ = "content_moderation_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    moderation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    safety_score: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation_score: Mapped[int] = mapped_column(Integer, nullable=False)
    safety_level: Mapped[str] = mapped_column(String(16), nullable=False)
    recommendation_level: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reviewer_user_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "content_type IN ('comment', 'space_post', 'playlist', 'user_profile')",
            name="chk_content_moderation_history_type",
        ),
        CheckConstraint(
            "source IN ('AGENT', 'MANUAL')",
            name="chk_content_moderation_history_source",
        ),
        CheckConstraint(
            "safety_score BETWEEN 0 AND 10 AND recommendation_score BETWEEN 0 AND 10",
            name="chk_content_moderation_history_scores",
        ),
        CheckConstraint(
            "safety_level IN ('SAFE', 'RISKY', 'DANGEROUS')",
            name="chk_content_moderation_history_safety_level",
        ),
        CheckConstraint(
            "recommendation_level IN ('NORMAL', 'RECOMMENDED')",
            name="chk_content_moderation_history_recommendation_level",
        ),
        Index(
            "idx_content_moderation_history_content",
            "content_type",
            "content_id",
            "created_at",
        ),
        Index(
            "idx_content_moderation_history_user",
            "user_id",
            "created_at",
        ),
    )


class UserContentModerationStats(Base):
    """用户当前有效审核结果的聚合统计。"""

    __tablename__ = "user_content_moderation_stats"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    risky_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    dangerous_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    recommended_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "risky_count >= 0 AND dangerous_count >= 0 AND recommended_count >= 0",
            name="chk_user_content_moderation_stats_nonnegative",
        ),
    )
