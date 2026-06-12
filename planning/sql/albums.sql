-- 专辑表
CREATE TABLE albums (
    id              BIGSERIAL PRIMARY KEY,
    title           VARCHAR(128) NOT NULL,                                                -- 专辑标题
    description     TEXT,                                                                   -- 专辑描述
    source          VARCHAR(50),                                                            -- 来源/出处
    collect_count   BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_albums_collect_count_nonnegative CHECK (collect_count >= 0),    -- 被收藏次数（反规范化计数，需应用层维护）
    play_count      BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_albums_play_count_nonnegative CHECK (play_count >= 0),          -- 播放次数（反规范化计数，需应用层维护）
    forward_count   BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_albums_forward_count_nonnegative CHECK (forward_count >= 0),    -- 转发次数（反规范化计数，需应用层维护）
    hot             SMALLINT DEFAULT 0 NOT NULL CONSTRAINT chk_albums_hot CHECK (hot >= 0 AND hot <= 1000),                  -- 热度值 0~1000
    cover_icon_url  VARCHAR(500),                                                           -- 封面图标 URL
    cover_url       VARCHAR(500),                                                           -- 主封面 URL
    is_deleted      BOOLEAN DEFAULT FALSE NOT NULL,                                         -- 软删除标记
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,                         -- 更新时间
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL                          -- 创建时间
);

-- 常用查询索引（排序、范围检索，仅活跃专辑）
CREATE INDEX idx_albums_hot ON albums (hot DESC) WHERE is_deleted = FALSE;
CREATE INDEX idx_albums_play_count ON albums (play_count DESC) WHERE is_deleted = FALSE;
CREATE INDEX idx_albums_collect_count ON albums (collect_count DESC) WHERE is_deleted = FALSE;
CREATE INDEX idx_albums_created_at ON albums (created_at DESC) WHERE is_deleted = FALSE;

-- 模糊查询索引（标题，仅活跃专辑）
CREATE INDEX idx_albums_title_trgm ON albums USING gin (title gin_trgm_ops) WHERE is_deleted = FALSE;

-- 触发器：自动更新 updated_at
CREATE TRIGGER trg_albums_updated_at
    BEFORE UPDATE ON albums
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();
