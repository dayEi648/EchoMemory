-- 风格字典
CREATE TABLE styles (
    id   SMALLINT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    CONSTRAINT uq_styles_name UNIQUE (name)
);
