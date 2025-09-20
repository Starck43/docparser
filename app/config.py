from pathlib import Path

from pydantic import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./docparser.db"
    UPLOAD_DIR: str = "uploads"
    SUPPORTED_FORMATS = [".docx", ".doc", ".pdf", ".txt"]

    # Настройки путей
    BASE_DIR = Path(__file__).parent
    DB_PATH = BASE_DIR / "database.db"
    DATA_DIR = BASE_DIR / "data"
    OUTPUT_DIR = BASE_DIR / "output"

    # Создание директорий, если они не существуют
    for directory in [DATA_DIR, OUTPUT_DIR]:
        directory.mkdir(exist_ok=True)

    # Максимальное количество файлов для обработки за один запуск (0 - без ограничений)
    MAX_FILES_TO_PROCESS = 0

    # Количество строк для отображения в консоли при порционном выводе
    CONSOLE_OUTPUT_BATCH_SIZE = 10

    # Настройки сохранения файлов
    AUTO_RENAME_ON_CONFLICT = True  # Автоматически добавлять индекс (-01, -02) при конфликте имен

    # Настройки валидации
    MAX_CUSTOMER_NAME_LENGTH = 100

    # Списки для валидации (можно будет дополнять)
    KNOWN_CUSTOMERS: list[str] = []  # Список известных контрагентов для проверки

    # Настройки парсера
    # Регулярные выражения для парсинга названия документа
    # Учитываем разные кавычки и произвольное количество пробелов
    PATTERN_CONTRACT = r"договор\s+[№N#]*\s*(\S+)"
    PATTERN_INVOICE = r"(?:счет\s*(?:на\s*оплату|фактура)?)[\s:]*[№N#]*\s*(\S+)"
    PATTERN_ACT = r"акт\s*(?:выполненных\s*работ|оказанных\s*услуг|сдачи-приемки)[\s:]*[№N#]*\s*(\S+)"


settings = Settings()
