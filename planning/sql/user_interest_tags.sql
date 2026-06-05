-- 用户兴趣标签关联（引用 interest_tags 字典）
CREATE TABLE user_interest_tags (
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interest_tag_id BIGINT NOT NULL REFERENCES interest_tags(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_interest_tags PRIMARY KEY (user_id, interest_tag_id)
);

CREATE INDEX idx_user_interest_tags_tag_id ON user_interest_tags (interest_tag_id);
