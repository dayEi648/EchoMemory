-- 启用 pg_trgm 扩展，用于昵称/用户名的模糊查询索引
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 用户表
CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(32)  NOT NULL,                       -- 登录用户名，全局唯一
    password_hash VARCHAR(255) NOT NULL,                       -- 密码哈希值（如 bcrypt）
    nickname      VARCHAR(32)  NOT NULL,                       -- 账号显示昵称
    email         VARCHAR(255),                                -- 绑定邮箱，可空
    phone         VARCHAR(20),                                 -- 绑定手机号，可空
    gender        SMALLINT DEFAULT 0 CONSTRAINT chk_users_gender CHECK (gender >= 0 AND gender <= 2),      -- 0=未知,1=男,2=女
    role          SMALLINT DEFAULT 0 CONSTRAINT chk_users_role CHECK (role >= 0 AND role <= 3),          -- 0=用户,1=VIP,2=管理员,3=超级管理员
    status        SMALLINT DEFAULT 0 CONSTRAINT chk_users_status CHECK (status >= 0 AND status <= 3),    -- 0=正常,1=禁言,2=限制,3=封号
    safety_score  SMALLINT DEFAULT 10 CONSTRAINT chk_users_safety_score CHECK (safety_score >= 0 AND safety_score <= 10), -- 安全指数 0~10
    is_deleted    BOOLEAN DEFAULT FALSE NOT NULL,             -- 软删除标记
    exp           INTEGER DEFAULT 0 NOT NULL CONSTRAINT chk_users_exp_nonnegative CHECK (exp >= 0),              -- 经验值，决定等级
    level         SMALLINT DEFAULT 0 NOT NULL CONSTRAINT chk_users_level_nonnegative CHECK (level >= 0),         -- 当前等级，由触发器自动维护
    city_id       SMALLINT REFERENCES cities(id),             -- 居住地字典 ID
    birth         DATE,                                        -- 出生日期
    bio           TEXT,                                        -- 个人简介
    is_verified   BOOLEAN DEFAULT FALSE NOT NULL,             -- 是否通过专业/官方认证
    like_count    BIGINT DEFAULT 0 NOT NULL CONSTRAINT chk_users_like_count_nonnegative CHECK (like_count >= 0), -- 收到的总点赞数（反规范化计数）
    avatar_url    VARCHAR(500),                                -- 头像图片 URL
    last_login_at TIMESTAMPTZ,                                 -- 最近一次登录时间
    banned_at     TIMESTAMPTZ,                                 -- 封禁/限制/禁言开始时间
    ban_duration  INTERVAL,                                    -- 封禁/限制/禁言持续时长
    updated_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,       -- 资料最后更新时间
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,       -- 账号创建时间
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT chk_users_ban_consistency CHECK (
        (banned_at IS NULL AND status NOT IN (1, 2, 3))
        OR (banned_at IS NOT NULL AND status IN (1, 2, 3))
    ),
    CONSTRAINT chk_users_ban_duration_positive CHECK (ban_duration IS NULL OR ban_duration > INTERVAL '0'),
    CONSTRAINT chk_users_ban_dates CHECK (ban_duration IS NULL OR banned_at IS NOT NULL)
);


-- 部分唯一索引：允许空值，非空时必须唯一
CREATE UNIQUE INDEX idx_users_email ON users (email) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX idx_users_phone ON users (phone) WHERE phone IS NOT NULL;

-- 常用查询索引（排序、过滤、范围检索）
CREATE INDEX idx_users_exp ON users (exp DESC);
CREATE INDEX idx_users_created_at ON users (created_at DESC);
CREATE INDEX idx_users_status ON users (status) WHERE is_deleted = FALSE;
CREATE INDEX idx_users_level ON users (level);
CREATE INDEX idx_users_last_login_at ON users (last_login_at DESC);
CREATE INDEX idx_users_banned_at ON users (banned_at) WHERE banned_at IS NOT NULL;

-- 模糊查询索引（GIN + trigram）
CREATE INDEX idx_users_nickname_trgm ON users USING gin (nickname gin_trgm_ops);
CREATE INDEX idx_users_username_trgm ON users USING gin (username gin_trgm_ops);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_updated_at();

CREATE TRIGGER trg_users_level_on_exp_change
    BEFORE INSERT OR UPDATE OF exp ON users
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_user_level();

-- 用户等级统计视图：实时计算下一级所需经验与进度
CREATE VIEW user_level_stats AS
SELECT
    u.id,
    u.exp,
    u.level,
    lc.title AS level_title,
    COALESCE(nlc.min_exp, u.exp) AS next_level_exp,
    CASE
        WHEN nlc.min_exp IS NULL THEN 100
        ELSE LEAST(100, GREATEST(0, ((u.exp - lc.min_exp) * 100) / NULLIF(nlc.min_exp - lc.min_exp, 0)))
    END AS level_progress
FROM users u
LEFT JOIN LATERAL (
    SELECT level, min_exp, title
    FROM level_config
    WHERE min_exp <= u.exp
    ORDER BY min_exp DESC
    LIMIT 1
) lc ON true
LEFT JOIN level_config nlc ON nlc.level = lc.level + 1;
