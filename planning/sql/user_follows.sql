-- 用户关注关系（粉丝/关注）
CREATE TABLE user_follows (
    follower_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followee_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_user_follows PRIMARY KEY (follower_id, followee_id),
    CONSTRAINT chk_user_follows_no_self_follow CHECK (follower_id <> followee_id)
);


CREATE INDEX idx_user_follows_followee ON user_follows (followee_id);
CREATE INDEX idx_user_follows_follower_time ON user_follows (follower_id, created_at DESC);
CREATE INDEX idx_user_follows_followee_time ON user_follows (followee_id, created_at DESC);
