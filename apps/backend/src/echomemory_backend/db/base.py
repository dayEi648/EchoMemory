"""定义 SQLAlchemy ORM 的声明性基类，供所有 ORM 模型继承。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    pass
