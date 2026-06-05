-- 评论点踩关联（替代原 comments.dislike_ids 数组）
CREATE TABLE comment_dislikes (
    comment_id BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_comment_dislikes PRIMARY KEY (comment_id, user_id)
);

-- 从用户方向查点踩过的评论
CREATE INDEX idx_comment_dislikes_user ON comment_dislikes (user_id);
