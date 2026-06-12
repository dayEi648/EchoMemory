-- 系统通知表（由系统生成，不可回复）
CREATE TABLE notifications (
    id           BIGSERIAL PRIMARY KEY,
    recipient_id BIGINT  NOT NULL REFERENCES users(id) ON DELETE CASCADE,          -- 接收者
    actor_id     BIGINT       REFERENCES users(id) ON DELETE SET NULL,             -- 触发者，允许为空
    type         SMALLINT NOT NULL,                                                -- 通知类型：0=被关注,1=评论被回复,2=评论被点赞,3=空间动态被点赞,4=空间动态被评论
    target_type  VARCHAR(20) NOT NULL,                                             -- 目标类型：user/comment/space_post
    target_id    BIGINT NOT NULL,                                                  -- 目标 ID
    is_read      BOOLEAN DEFAULT FALSE NOT NULL,                                   -- 是否已读
    extra        JSONB DEFAULT '{}' NOT NULL,                                      -- 冗余上下文（评论/动态预览等）
    created_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT chk_notifications_type CHECK (type >= 0 AND type <= 4),
    CONSTRAINT chk_notifications_target_type CHECK (target_type IN ('user', 'comment', 'space_post')),
    CONSTRAINT chk_notifications_no_self CHECK (actor_id IS NULL OR actor_id <> recipient_id)
);

-- 按接收者时间倒序查询
CREATE INDEX idx_notifications_recipient_time ON notifications (recipient_id, created_at DESC);

-- 未读通知快速查询
CREATE INDEX idx_notifications_recipient_unread ON notifications (recipient_id) WHERE is_read = FALSE;

-- 未读时幂等：同一 (recipient, actor, type, target) 不重复入库
CREATE UNIQUE INDEX uq_notifications_dedupe_unread
    ON notifications (recipient_id, actor_id, type, target_type, target_id)
    WHERE is_read = FALSE;
