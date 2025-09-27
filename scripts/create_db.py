import sys
import os
from pathlib import Path

from app.config import settings
from app.db import init_db
from app.utils.console import confirm_prompt, console


def delete_database():
    """Удаляет существующую базу данных, если она существует."""
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    
    if db_path.exists():
        try:
            os.remove(db_path)
            print(f"✅ Удалена старая база данных: {db_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка при удалении базы данных: {e}")
            return False
    return True


def create_database():
    """
    Создает все таблицы в базе данных.
    ВНИМАНИЕ: Удаляет существующую базу данных, если она есть.
    """
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    
    if db_path.exists():
        print("\n" + "=" * 60)
        print("⚠️ ВНИМАНИЕ: БАЗА ДАННЫХ УЖЕ СУЩЕСТВУЕТ!")
        print(f"Путь к базе данных: {db_path}")
        print("Все существующие данные будут удалены!")
        print("=" * 60)

        if not confirm_prompt("Будут удалены все существующие данные. Продолжить?", default=False):
            console.print("\nОтменено пользователем.")
            sys.exit(0)
    
    # Удаляем существующую базу данных
    if not delete_database():
        sys.exit(1)
    
    # Создаем новую базу данных и таблицы
    try:
        print("\nСоздание таблиц в базе данных...")
        init_db()
        print("\n✅ База данных успешно пересоздана!")
        print(f"Расположение: {settings.DATABASE_URL.replace('sqlite:///', '')}")
        print("=" * 70 + "\n")
    except Exception as e:
        print(f"\n❌ Ошибка при создании базы данных: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_database()
