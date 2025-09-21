from pathlib import Path


class Settings:
    DATABASE_URL: str = "sqlite:///./docparser.db"
    UPLOAD_DIR: str = "uploads"
    SUPPORTED_FORMATS = [".docx", ".doc", ".pdf", ".txt"]

    # Настройки путей
    BASE_DIR = Path(__file__).parent.parent
    DB_PATH = BASE_DIR / "database.db"
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / "output"

    # Максимальное количество файлов для обработки за один запуск (0 - без ограничений)
    MAX_FILES_TO_PROCESS = 0

    # Количество строк для отображения в консоли при порционном выводе
    CONSOLE_OUTPUT_BATCH_SIZE = 10

    # Настройки сохранения файлов
    AUTO_RENAME_ON_CONFLICT = True  # Автоматически добавлять индекс (-01, -02) при конфликте имен

    # Настройки валидации
    MAX_CUSTOMER_NAME_LENGTH = 100

    # Новые настройки для парсинга покупателей
    EXCLUDE_NAME_LIST: list[str] = [
        "Холдинг Плюс",
        "«Покупатель»",
        "«Поставщик»"
    ]

    LEGAL_ENTITY_PATTERNS: list[str] = [
        "ООО",
        "АО",
        "ОАО",
        "ПАО",
        "ИП",
        "Общество с ограниченной ответственностью",
        "Акционерное общество",
        "Публичное акционерное общество",
        "Индивидуальный предприниматель"
    ]

    def __init__(self):
        # Создание директорий, если они не существуют
        for directory in [self.DATA_DIR, self.OUTPUT_DIR]:
            directory.mkdir(exist_ok=True)


settings = Settings()
