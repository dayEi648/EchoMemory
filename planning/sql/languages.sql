-- 语言字典
CREATE TABLE languages (
    id   SMALLSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    CONSTRAINT uq_languages_name UNIQUE (name)
);
