-- 歌单表
CREATE TABLE playlists (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(128) NOT NULL,                                                -- 歌单标题
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,               -- 创建者
    is_private      BOOLEAN DEFAULT FALSE NOT NULL,                                       -- 是否私密
    description     TEXT,                                                                   -- 歌单简介
    collect_count   BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_playlists_collect_count_nonnegative CHECK (collect_count >= 0),    -- 被收藏次数（反规范化计数，需应用层维护）
    play_count      BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_playlists_play_count_nonnegative CHECK (play_count >= 0),          -- 播放次数（反规范化计数，需应用层维护）
    hot             SMALLINT DEFAULT 0 NOT NULL CONSTRAINT chk_playlists_hot CHECK (hot >= 0 AND hot <= 1000),                  -- 热度值 0~1000
    comment_count   BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_playlists_comment_count_nonnegative CHECK (comment_count >= 0),    -- 评论数（反规范化计数，需应用层维护）
    is_like         BOOLEAN DEFAULT FALSE NOT NULL,                                       -- 是否为"喜欢"歌单（每个用户仅一个）
    is_recommended  BOOLEAN DEFAULT FALSE NOT NULL,                                       -- 是否平台推荐
    cover_icon_url  VARCHAR(500),                                                           -- 封面图标 URL
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,                                  -- 更新时间
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL                          -- 创建时间
);

-- 每个用户只能有一个"喜欢"歌单
CREATE UNIQUE INDEX idx_playlists_unique_user_like ON playlists (user_id) WHERE is_like = TRUE;

-- 常用查询索引
CREATE INDEX idx_playlists_user_id ON playlists (user_id);
CREATE INDEX idx_playlists_hot ON playlists (hot DESC);
CREATE INDEX idx_playlists_play_count ON playlists (play_count DESC);
CREATE INDEX idx_playlists_collect_count ON playlists (collect_count DESC);
CREATE INDEX idx_playlists_created_at ON playlists (created_at DESC);

-- 模糊查询索引（标题）
CREATE INDEX idx_playlists_title_trgm ON playlists USING gin (title gin_trgm_ops);

-- 触发器：自动更新 updated_at
CREATE TRIGGER trg_playlists_updated_at
    BEFORE UPDATE ON playlists
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();
