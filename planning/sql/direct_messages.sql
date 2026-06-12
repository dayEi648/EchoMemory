-- 私信消息条目表
CREATE TABLE direct_messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,                                                 -- 纯文本内容，上限 2000 字符（应用层校验）
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_direct_messages_conversation_time ON direct_messages (conversation_id, created_at DESC);
CREATE INDEX idx_direct_messages_sender ON direct_messages (sender_id);

-- 补充 conversations.last_message_id 外键（避免循环依赖导致建表失败）
ALTER TABLE conversations
    ADD CONSTRAINT fk_conversations_last_message_id
    FOREIGN KEY (last_message_id) REFERENCES direct_messages(id)
    ON DELETE SET NULL;
