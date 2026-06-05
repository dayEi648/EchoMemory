-- 音乐表
CREATE TABLE musics (
    id              BIGSERIAL PRIMARY KEY,                                                -- 音乐唯一标识
    title           VARCHAR(128) NOT NULL,                                                -- 音乐标题
    is_vip          BOOLEAN DEFAULT FALSE NOT NULL,                                      -- 是否需要 VIP
    source          VARCHAR(50),                                                          -- 来源/出处
    style_id        SMALLINT REFERENCES styles(id),                                       -- 风格/流派字典 ID
    language_id     SMALLINT REFERENCES languages(id),                                    -- 语言字典 ID
    collect_count   BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_musics_collect_count_nonnegative CHECK (collect_count >= 0),    -- 被收藏次数（反规范化计数，需应用层维护）
    hot             SMALLINT DEFAULT 0 NOT NULL CONSTRAINT chk_musics_hot CHECK (hot >= 0 AND hot <= 1000),                  -- 热度值 0~1000
    comment_count   BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_musics_comment_count_nonnegative CHECK (comment_count >= 0),    -- 评论数（反规范化计数，需应用层维护）
    play_count      BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_musics_play_count_nonnegative CHECK (play_count >= 0),          -- 播放次数（反规范化计数，需应用层维护）
    is_published    BOOLEAN DEFAULT FALSE NOT NULL,                                      -- 是否上架
    release_date    DATE,                                                                 -- 发行日期
    file_url        VARCHAR(500),                                                         -- 音频文件 URL
    lyrics_url      VARCHAR(500),                                                         -- 歌词文件 URL
    cover_icon_url  VARCHAR(500),                                                         -- 封面图标 URL
    cover_home_url  VARCHAR(500),                                                         -- 首页封面 URL
    cover_play_url  VARCHAR(500),                                                         -- 播放页封面 URL
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,                      -- 创建时间
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL                       -- 更新时间
);

-- 常用查询索引（排序、过滤、范围检索）
CREATE INDEX idx_musics_release_date ON musics (release_date DESC);
CREATE INDEX idx_musics_hot ON musics (hot DESC);
CREATE INDEX idx_musics_play_count ON musics (play_count DESC);
CREATE INDEX idx_musics_collect_count ON musics (collect_count DESC);
CREATE INDEX idx_musics_created_at ON musics (created_at DESC);
CREATE INDEX idx_musics_style_id ON musics (style_id);
CREATE INDEX idx_musics_language_id ON musics (language_id);
-- 模糊查询索引（标题）
CREATE INDEX idx_musics_title_trgm ON musics USING gin (title gin_trgm_ops);

-- 触发器：自动更新 updated_at
CREATE TRIGGER trg_musics_updated_at
    BEFORE UPDATE ON musics
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();


