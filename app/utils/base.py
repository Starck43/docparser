import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import docx
import pdfplumber

from app.config import settings
from app.services.tables import clean_table_data
from app.utils.console import confirm_prompt


def is_supported(file: Path) -> bool:
	"""Проверить, что файл имеет поддерживаемое расширение"""
	return file.suffix.lower() in settings.SUPPORTED_FORMATS


def extract_text_from_pdf(path: str) -> str:
	"""
	Извлекает текст И таблицы из PDF используя pdfplumber.
	Возвращает структурированный текст с таблицами.
	"""
	try:
		texts = []
		with pdfplumber.open(path) as pdf:
			for page in pdf.pages:
				page_text = page.extract_text()
				if page_text:
					texts.append(page_text)
		return "\n".join(texts).strip()
	except Exception as e:
		print(f"Ошибка извлечения текста: {e}")
		return ""


def extract_tables_from_pdf(path: str) -> list[list[list[str]]]:
	"""
	Извлекает и очищает таблицы из PDF.
	"""
	try:
		all_tables = []
		with pdfplumber.open(path) as pdf:
			for page in pdf.pages:
				tables = page.extract_tables()
				for table in tables:
					if table:
						cleaned_table = clean_table_data(table)
						if cleaned_table and len(cleaned_table) > 1:
							all_tables.append(cleaned_table)
		return all_tables
	except Exception as e:
		print(f"Ошибка извлечения таблиц: {e}")
		return []


def extract_text_from_txt(path: str) -> str:
	"""Извлечение текста из TXT"""
	try:
		with open(path, "r", encoding="utf-8", errors="ignore") as f:
			return f.read()
	except Exception as e:
		print(f"Ошибка чтения TXT: {e}")
		return ""


def extract_text_from_docx(path: str) -> str:
	"""Извлечение текста из DOCX"""
	try:
		doc = docx.Document(path)
		return "\n".join(paragraph.text for paragraph in doc.paragraphs)
	except Exception as e:
		print(f"Ошибка чтения DOCX: {e}")
		return ""


def extract_text_from_file(path: Path) -> str:
	"""
	Универсальный парсер: выбирает логику по расширению.
	Возвращает извлечённый текст (может быть пустой строкой).
	"""
	if not is_supported(path):
		raise ValueError(f"Формат {path.suffix} не поддерживается")

	suffix = path.suffix.lower()

	if suffix == ".pdf":
		return extract_text_from_pdf(str(path))
	elif suffix == ".txt":
		return extract_text_from_txt(str(path))
	elif suffix in [".docx", ".doc"]:
		return extract_text_from_docx(str(path))
	else:
		# Пробуем как текст
		try:
			return extract_text_from_txt(str(path))
		except:
			return ""


def get_current_year() -> int:
	"""
	Возвращает текущий год.
	Используется как значение по умолчанию при парсинге.
	"""
	return datetime.now().year


def get_unique_filename(
		directory: Path,
		base_name: str,
		postfix: str = "",
		extension: str = ".xlsx",
		force_overwrite: bool = False
) -> Path:
	"""
	Генерирует уникальное имя файла, добавляя индекс если файл уже существует.

	Args:
		directory: Папка для сохранения
		base_name: Базовое имя файла (без расширения)
		extension: Расширение файла (по умолчанию .xlsx)
		postfix: Дополнительное окончание к имени файла
		force_overwrite: Принудительная перезапись существующего файла

	Returns:
		Путь к уникальному файлу
	"""
	# Если force_overwrite=True, просто возвращаем путь без проверок
	if force_overwrite:
		filename = f"{base_name}{postfix}{extension}"
		return directory / filename

	counter = 1
	while True:
		if counter == 1:
			filename = f"{base_name}{postfix}{extension}"
		else:
			filename = f"{base_name}{postfix}-{counter:02d}{extension}"

		file_path = directory / filename

		if not file_path.exists():
			return file_path

		# Предлагаем пользователю выбрать действие
		if confirm_prompt(
				f"Файл {filename} уже существует. Перезаписать?",
				default=False  # По умолчанию "Нет" для безопасности
		):
			return file_path
		else:
			counter += 1


def format_string_list(
		string_list: list[str] | str | None,
		default_text: str = "—",
		max_line_length: Optional[int] = None,
		separator: str = "\n"
) -> str:
	"""
	Форматирует список строк для отображения.

	Args:
		string_list: Список строк для форматирования
		default_text: Текст если список пустой
		max_line_length: Максимальная длина каждой строки
		separator: Разделитель между строками

	Returns:
		Отформатированная строка
	"""
	if not string_list:
		return default_text

	# Нормализуем входные данные к списку строк
	if isinstance(string_list, str):
		try:
			# Пробуем распарсить JSON строку
			parsed = json.loads(string_list)
			lines = parsed if isinstance(parsed, list) else [parsed]
		except (json.JSONDecodeError, TypeError):
			lines = [string_list]
	else:
		lines = string_list

	if not lines:
		return default_text

	# Обрабатываем обрезание строк
	if max_line_length:
		formatted_lines = []
		for line in lines:
			line_str = str(line)  # На случай если не строка
			if len(line_str) > max_line_length:
				formatted_lines.append(line_str[:max_line_length] + "...")
			else:
				formatted_lines.append(line_str)
		return separator.join(formatted_lines)
	else:
		return separator.join(str(line) for line in lines)
