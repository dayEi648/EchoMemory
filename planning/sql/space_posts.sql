-- 个人空间说说表
CREATE TABLE space_posts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content TEXT,                                                                   -- 正文内容
    post_type VARCHAR(20) NOT NULL DEFAULT 'original',                             -- original=原创, forward=转发
    source_id BIGINT,                                                               -- 转发源ID（多态关联，具体表由 source_type 决定）
    source_type VARCHAR(20),                                                        -- 转发源类型: post/music/playlist/...
    extra JSONB DEFAULT '{}',                                                       -- 转发快照（原源删除后保留信息）
    is_private BOOLEAN DEFAULT FALSE NOT NULL,                                      -- 是否私密
    comment_count BIGINT DEFAULT 0 NOT NULL,                                        -- 评论数（反规范化计数，需应用层维护）
    forward_count BIGINT DEFAULT 0 NOT NULL,                                        -- 转发数（反规范化计数，需应用层维护）
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,                               -- 更新时间
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,                      -- 创建时间
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,                                      -- 软删除标记

    CONSTRAINT chk_space_posts_post_type CHECK (post_type IN ('original', 'forward')),
    CONSTRAINT chk_space_posts_source_consistency CHECK (
        (post_type = 'original' AND source_id IS NULL AND source_type IS NULL)
        OR (post_type = 'forward' AND source_id IS NOT NULL AND source_type IS NOT NULL)
    )
);

-- 索引：查某用户的说说列表（核心查询，仅公开内容）
CREATE INDEX idx_space_posts_user_time ON space_posts (user_id, created_at DESC) WHERE is_deleted = FALSE AND is_private = FALSE;

-- 索引：时间线排序（仅公开内容）
CREATE INDEX idx_space_posts_created_at ON space_posts (created_at DESC) WHERE is_deleted = FALSE AND is_private = FALSE;

-- 触发器：自动更新 updated_at
CREATE TRIGGER trg_space_posts_updated_at
    BEFORE UPDATE ON space_posts
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();
