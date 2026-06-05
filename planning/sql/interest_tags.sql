-- 兴趣标签字典（全局共享，由音乐标签聚合而成）
CREATE TABLE interest_tags (
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    CONSTRAINT uq_interest_tags_name UNIQUE (name)
);
