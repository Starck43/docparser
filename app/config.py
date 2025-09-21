from pathlib import Path


class Settings:

    # Настройки путей
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data"
    EXPORT_DIR = BASE_DIR / "export"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/docparser.db"
    SQL_DEBUG_MODE = False  # при True отображаются SQL запросы в консоли

    SUPPORTED_FORMATS = [".docx", ".doc", ".pdf", ".txt"]

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
        for directory in [self.DATA_DIR, self.EXPORT_DIR]:
            directory.mkdir(exist_ok=True)


settings = Settings()
