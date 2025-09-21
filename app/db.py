from sqlmodel import create_engine, Session, SQLModel
from typing import Iterator
from app.config import settings

# Импортируем все модели, чтобы они зарегистрировались в SQLModel.metadata
from app.models import Document, ProductPlan  # noqa: F401

# Создаем движок БД с отладочным выводом
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_DEBUG_MODE,  # Включаем отладочный вывод при необходимости
    connect_args={"check_same_thread": False}  # Требуется для SQLite
)


def init_db() -> None:
    """Инициализирует базу данных, создавая все таблицы."""

    print("Creating database tables...")
    print(f"Tables to create: {list(SQLModel.metadata.tables.keys())}")
    
    # Создаем все таблицы
    SQLModel.metadata.create_all(engine)
    print("Database tables created successfully!")


def get_db() -> Iterator[Session]:
    """Генератор сессий SQLModel."""
    with Session(engine) as session:
        yield session
