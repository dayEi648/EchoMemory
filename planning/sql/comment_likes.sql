-- 评论点赞关联（替代原 comments.like_ids 数组）
CREATE TABLE comment_likes (
    comment_id BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_comment_likes PRIMARY KEY (comment_id, user_id)
);

-- 从用户方向查点赞过的评论（如"我的点赞列表"）
CREATE INDEX idx_comment_likes_user ON comment_likes (user_id);
