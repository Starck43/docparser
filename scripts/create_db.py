from app.config import settings
from app.db import init_db


def create_database():
	"""Создает все таблицы в базе данных."""
	print(f"Создание базы данных: {settings.DATABASE_URL}")
	init_db()
	print("База данных успешно создана!")


if __name__ == "__main__":
	create_database()
