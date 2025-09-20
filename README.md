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
├── README.md
├── requirements.txt
├── .gitignore
├── cli.py
├── scripts/
│   └── create_db.py
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   └── services/
│       ├── __init__.py
│       ├── utils.py
│       └── parser.py
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
