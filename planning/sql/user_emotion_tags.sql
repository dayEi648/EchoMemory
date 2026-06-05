-- 用户情绪标签关联（引用 emotion_tags 字典）
CREATE TABLE user_emotion_tags (
    user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emotion_tag_id BIGINT NOT NULL REFERENCES emotion_tags(id) ON DELETE CASCADE,
    created_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_emotion_tags PRIMARY KEY (user_id, emotion_tag_id)
);

CREATE INDEX idx_user_emotion_tags_tag_id ON user_emotion_tags (emotion_tag_id);
