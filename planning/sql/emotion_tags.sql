-- 情绪标签字典（全局共享，由音乐标签聚合而成）
CREATE TABLE emotion_tags (
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    CONSTRAINT uq_emotion_tags_name UNIQUE (name)
);
