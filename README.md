# docParser

Утилита для парсинга документов (PDF, DOCX, TXT) с сохранением данных и экспортом в файл (SQLite).

## Что делает
- Извлекает текст из `.txt`, `.docx`, `.pdf`.
- Сохраняет результаты в SQLite.
- Экспортирует данные в `.xlsx`.
- Управляется через CLI (`cli.py`).

## Системные зависимости
- Python 3.10+


## 🗂 Структура проекта
```
docparser/
├── .env.example # Конфигурация окружения (образец)
├── .gitignore # Игнорируемые файлы Git
├── README.md # Документация
├── cli.py # 📌 Основной интерфейс командной строки
├── main.py # 🚀 Точка входа в приложение
├── requirements.txt # Зависимости Python
├── docparser.db # 🗄️ Файл базы данных SQLite
│
├── app/ # Основной пакет приложения
│   ├── config.py # ⚙️ Конфигурация приложения
│   ├── crud.py # 🛠️ CRUD-операции с базой данных
│   ├── db.py # 🔌 Подключение к базе данных
│   ├── models.py # 🏗️ Модели SQLAlchemy таблиц
│   │
│   ├── services/ # 🧩 Бизнес-логика приложения
│   └── utils/ # 🛠️ Вспомогательные утилиты
│
├── data/ # 📂 Входные документы для обработки
├── export/ # 📁 Результаты экспорта
│
├── scripts/ # 📜 Вспомогательные скрипты
│   └── create_db.py # 🛠️ Инициализация базы данных
│
└── tests/ # 🧪 Тесты
    └── test_parser.py # Тесты парсера
```

## 🚀 Быстрый старт

### Установка проекта из GitHub

```bash
git clone https://github.com/Starck43/docparser.git
cd docparser
````

### Установка окружения Python и зависимостей приложения
```bash
# Linux / macOS
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Быстрый запуск
```bash
# Создайте и отредактируйте .env файл со своими настройками. Образец в .env.example
cp .env.example .env

# Инициализация базы
python -m scripts.create_db 

# Запуск парсинга
python main.py

# Распарсить папку с документами
python cli.py parse --data-dir /mnt/shared/docs      # Linux
python cli.py parse --data-dir D:\Shared\Docs        # Windows

# Парсинг документов
python cli.py parse [--data-dir PATH] [--year YEAR] [--limit N] [--dry-run] [--batch-size N]
```
--data-dir - папка с документами (по умолчанию: ./data)

--year - год для фильтрации (по умолчанию: текущий год)

--limit - лимит файлов для обработки (0 = без ограничений)

--dry-run - предпросмотр результатов парсинга без сохранения в БД

--batch-size - количество документов для отображения в консоли

```bash
# Экспорт в Excel
python cli.py export [--year YEAR] [--output-dir PATH] [--limit N] [--max-per-file N] [--force]
```
--year - год для экспорта (по умолчанию: текущий год)

--output-dir - папка для сохранения (по умолчанию: ./export)

--limit - лимит документов для экспорта

--dry-run - предпросмотр сохраненных данных в БД без экспортирования в файл

--max-per-file - максимум документов в одном файле

--force - принудительная перезапись существующих файлов

```bash
# Просмотр ошибок
python cli.py errors [--year YEAR] [--limit N]
```

--year - год для фильтрации

--limit - лимит документов для показа


```bash
# Статистика
python cli.py stats [--year YEAR]
```
--year - год для статистики


```bash
# Очистка базы данных
python cli.py clear-db --confirm
```
--confirm - подтверждение очистки (обязательно)


```bash
# Помощь по командам
python cli.py --help
python cli.py [command] --help
```
