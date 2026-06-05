-- 说说点赞关联（替代原 space_posts.like_ids 数组）
CREATE TABLE space_post_likes (
    post_id    BIGINT NOT NULL REFERENCES space_posts(id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_space_post_likes PRIMARY KEY (post_id, user_id)
);

-- 从用户方向查点赞过的说说（如"我的点赞列表"）
CREATE INDEX idx_space_post_likes_user ON space_post_likes (user_id);
