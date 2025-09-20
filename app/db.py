from sqlmodel import create_engine, Session, SQLModel
from typing import Iterator
from app.config import settings

# Создаем движок БД
engine = create_engine(settings.DATABASE_URL, echo=False)


def init_db() -> None:
	"""Инициализирует базу данных, создавая все таблицы."""
	SQLModel.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
	"""Генератор сессий SQLModel."""
	with Session(engine) as session:
		yield session
