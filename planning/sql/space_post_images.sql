-- 说说图片关联（替代原 space_posts.images 数组）
CREATE TABLE space_post_images (
    post_id    BIGINT NOT NULL REFERENCES space_posts(id) ON DELETE CASCADE,
    image_url  VARCHAR(500) NOT NULL,
    ordinal    SMALLINT DEFAULT 0 NOT NULL, -- 图片排序位
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_space_post_images PRIMARY KEY (post_id, ordinal),
    CONSTRAINT chk_space_post_images_ordinal_nonnegative CHECK (ordinal >= 0)
);

-- post_id 已在主键中索引，无需额外建索引。
