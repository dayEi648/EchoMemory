-- 评论表
CREATE TABLE comments (
    id BIGSERIAL PRIMARY KEY,

    -- 评论目标（三选一，有 CHECK 约束保证只有一个非空）
    music_id BIGINT REFERENCES musics(id) ON DELETE CASCADE,
    playlist_id BIGINT REFERENCES playlists(id) ON DELETE CASCADE,
    space_post_id BIGINT REFERENCES space_posts(id) ON DELETE CASCADE,

    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    reply_count INTEGER DEFAULT 0 NOT NULL,

    -- 层级关系
    -- 表层评论: parent_id IS NULL, root_id IS NULL, is_nested_reply = false
    -- 里层普通回复: parent_id = root_id, is_nested_reply = false
    -- 里层嵌套回复("@user"): parent_id != root_id, is_nested_reply = true
    parent_id BIGINT REFERENCES comments(id) ON DELETE CASCADE,
    root_id BIGINT REFERENCES comments(id) ON DELETE CASCADE,
    is_nested_reply BOOLEAN DEFAULT FALSE NOT NULL,

    safety SMALLINT DEFAULT 10 NOT NULL CONSTRAINT chk_comments_safety CHECK (safety >= 0 AND safety <= 10),
    is_recommended BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,

    like_count BIGINT DEFAULT 0 NOT NULL,
    dislike_count BIGINT DEFAULT 0 NOT NULL,

    CONSTRAINT chk_comment_target_unique CHECK (
        (music_id IS NOT NULL)::int +
        (playlist_id IS NOT NULL)::int +
        (space_post_id IS NOT NULL)::int = 1
    )
);

-- 索引：查某音乐/歌单/空间的表层评论（最核心查询，部分索引）
CREATE INDEX idx_comments_music_root ON comments (music_id, created_at DESC) WHERE parent_id IS NULL AND is_deleted = FALSE;
CREATE INDEX idx_comments_playlist_root ON comments (playlist_id, created_at DESC) WHERE parent_id IS NULL AND is_deleted = FALSE;
CREATE INDEX idx_comments_space_root ON comments (space_post_id, created_at DESC) WHERE parent_id IS NULL AND is_deleted = FALSE;

-- 索引：查某表层评论下的所有里层回复
CREATE INDEX idx_comments_root_time ON comments (root_id, created_at DESC);

-- 索引：查某用户的所有评论
CREATE INDEX idx_comments_user_id ON comments (user_id);

-- 触发器：自动更新 updated_at
CREATE TRIGGER trg_comments_updated_at
    BEFORE UPDATE ON comments
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();
