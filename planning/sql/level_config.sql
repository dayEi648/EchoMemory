-- 等级配置表：定义等级阈值，与 users 表解耦，便于随时调整升级曲线
CREATE TABLE level_config (
    level   SMALLINT PRIMARY KEY,
    min_exp INTEGER  NOT NULL,
    title   VARCHAR(50)
);

CREATE INDEX idx_level_config_min_exp ON level_config(min_exp);
