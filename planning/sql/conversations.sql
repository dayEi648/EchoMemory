-- 私信会话元数据表（每对用户至多一条记录）
CREATE TABLE conversations (
    id                 BIGSERIAL PRIMARY KEY,
    user1_id           BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,     -- 较小用户 ID
    user2_id           BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,     -- 较大用户 ID
    last_message_id    BIGINT,                                                     -- 最后一条消息 ID（外键在 direct_messages.sql 中补充）
    user1_unread_count BIGINT DEFAULT 0 NOT NULL,                                  -- user1 未读数
    user2_unread_count BIGINT DEFAULT 0 NOT NULL,                                  -- user2 未读数
    updated_at         TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_at         TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT chk_conversations_user_order CHECK (user1_id < user2_id),
    CONSTRAINT chk_conversations_user1_unread_nonneg CHECK (user1_unread_count >= 0),
    CONSTRAINT chk_conversations_user2_unread_nonneg CHECK (user2_unread_count >= 0),
    CONSTRAINT uq_conversations_user_pair UNIQUE (user1_id, user2_id)
);

CREATE INDEX idx_conversations_user1_time ON conversations (user1_id, updated_at DESC);
CREATE INDEX idx_conversations_user2_time ON conversations (user2_id, updated_at DESC);
