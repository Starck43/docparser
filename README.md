# DocParser

Утилита для парсинга документов (PDF, DOCX, TXT) с сохранением текста в базу данных (SQLite).

## Что делает
- Извлекает текст из `.txt`, `.docx`, `.pdf`.
- Сохраняет результаты в SQLite.
- Экспортирует данные в `.xlsx`.
- Управляется через CLI (`cli.py`).

## Системные зависимости
- Python 3.10+


## Структура проекта
```sourcegraph
docparser/
├── app/
│   ├── config.py          # Настройки (Settings класс)
│   ├── db.py             # Инициализация БД
│   ├── main.py           # CLI с Typer
│   ├── models.py         # SQLModel модели
│   ├── services/
│   │   ├── document_parser.py  # Парсер структурированных данных
│   │   └── utils.py            # Утилиты (is_supported и др.)
│   └── utils/
│       └── file_utils.py       # Работа с файлами
├── data/                 # Исходные документы
├── output/               # Обработанные документы
├── scripts/
│   └── create_db.py      # Скрипт создания БД
└── tests/
    └── test_parser.py
```

### Установка (пример)
```bash
# Linux / macOS
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# создать базу
python scripts/create_db.py
```

### Быстрый запуск
```bash
# Инициализация базы
python scripts/create_db.py

# Распарсить папку с документами
python cli.py parse-folder /mnt/shared/docs      # Linux
python cli.py parse-folder D:\Shared\Docs        # Windows

# Распарсить один файл
python cli.py parse-file example.docx

# пример curl:
curl -F "file=@/path/to/doc.pdf" /upload
```
