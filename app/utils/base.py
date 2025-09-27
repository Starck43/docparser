import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from slugify import slugify

from app.config import settings


def is_supported(file: Path) -> bool:
	"""Проверить, что файл имеет поддерживаемое расширение"""
	return file.suffix.lower() in settings.SUPPORTED_FORMATS


def get_current_year() -> int:
	"""
	Возвращает текущий год.
	Используется как значение по умолчанию при парсинге.
	"""
	return datetime.now().year


def parse_range_string(range_str: str | None, total: int = None) -> tuple[int | None, int | None]:
	"""
	Парсит строку диапазона в offset и limit из человеческого представления

	:param range_str: Строка диапазона ('1-10', ':10', '5:', etc.)
	:param total: Общее количество документов
	:return: Кортеж (offset, limit)
	"""
	if not range_str or range_str.strip().lower() == "all":
		return None, None  # Все документы

	range_str = range_str.strip()
	normalized_range = range_str.replace(':', '-').replace(' ', '')

	match = re.match(r'^(\d*)\s*-\s*(\d*)$', normalized_range)
	if match:
		start_part, end_part = match.groups()

		try:
			# Начало диапазона (1-based → 0-based)
			start = int(start_part) - 1 if start_part else 0

			# Конец диапазона (обработка случая "5-")
			if end_part:
				end = int(end_part)
			else:
				end = total  # Если конец не указан - до конца списка

			# Проверка корректности
			if start < 0:
				raise ValueError(f"Начало диапазона не может быть отрицательным: {start + 1}")

			if total is not None:  # Если известно общее количество
				if start >= total:
					raise ValueError(f"Начало диапазона ({start + 1}) превышает общее количество документов ({total})")
				if end is not None and end > total:
					end = total  # Ограничиваем конец максимальным количеством
				if end is not None and end <= start:
					raise ValueError(f"Конец диапазона должен быть больше начала: {start + 1}-{end}")

			# Вычисляем limit только если end указан
			if end is not None:
				limit = end - start
				if limit <= 0:
					raise ValueError(f"Результирующий лимит должен быть положительным: {limit}")
			else:
				# Если end не указан (диапазон "9-") и total неизвестен - limit = None (все документы)
				limit = None

		except ValueError as e:
			raise ValueError(f"Некорректный диапазон '{range_str}': {e}")

	elif normalized_range.isdigit():
		limit = int(normalized_range)
		if limit <= 0:
			raise ValueError(f"Лимит должен быть положительным: {limit}")
		if total is not None and limit > total:
			limit = total
		return 0, limit

	else:
		raise ValueError(f"Некорректный формат диапазона: '{range_str}'. Используйте: '1-10', ':10', '5-', 'all'")

	return start, limit


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


def normalize_date(date_str: str = "") -> Optional[str]:
	"""Пробует распознать дату вида мес.год → 01.2025"""
	date_str = date_str.strip().lower()

	if not date_str:
		return None

	# 1. Формат: 06.2025 или 06/2025 или 6.25 или 6/25
	m = re.search(r'(\d{1,2})[./](\d{2,4})', date_str)
	if m:
		month, year_val = m.groups()
		month = int(month)
		if 1 <= month <= 12:
			if len(year_val) == 2:
				year_val = "20" + year_val
			return f"{month:02d}.{year_val}"

	# 2. Формат: янв.26, фев2025, март 2025 и т.д.
	m2 = re.search(r'(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[а-я]*\.?\s*(\d{2,4})', date_str)
	if m2:
		months = {
			"янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "июн": 6,
			"июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12
		}
		month_key = m2.group(1).lower()[:3]
		if month_key in months:
			month = months[month_key]
			year_val = m2.group(2)
			if len(year_val) == 2:
				year_val = "20" + year_val
			return f"{month:02d}.{year_val}"

	# 3. Формат: январь 2025, ФЕВРАЛЬ 2025 и т.д. (полные названия)
	full_months = {
		"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
		"июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12
	}

	for name, num in full_months.items():
		if name in date_str.lower():
			# Ищем год после названия месяца
			year_match = re.search(r'(\d{4})', date_str)
			if year_match:
				return f"{num:02d}.{year_match.group(1)}"
			# Если год из двух цифр
			year_match = re.search(r'(\d{2})(?:\D|$)', date_str)
			if year_match:
				return f"{num:02d}.20{year_match.group(1)}"

	# 4. Формат: 01.2025г., 01.2025 г., 01.2025г
	m3 = re.search(r'(\d{1,2})[./](\d{4})\s*г', date_str, re.IGNORECASE)
	if m3:
		month, year_val = m3.groups()
		month = int(month)
		if 1 <= month <= 12:
			return f"{month:02d}.{year_val}"

	return None


def slugify_filename(filename: str) -> str:
	"""
	Преобразует имя файла в slug-формат БЕЗ расширения.
	Пример: 'КОМПАНИЯ Т, 331222, 202501-202512.pdf' -> 'kompanija-331222-202501-202512'
	"""
	name = Path(filename).stem
	return slugify(
		name,
		lowercase=True,  # в нижний регистр
		separator='-',  # разделитель
		regex_pattern=r'[^-a-z0-9]+'  # разрешенные символы
	)


def get_localized_months_list(lang: str = 'ru_RU') -> list[str]:
	"""Возвращает локализованные сокращения месяцев"""

	import calendar
	import locale

	try:
		locale.setlocale(locale.LC_TIME, lang)

		# Получаем сокращенные названия месяцев
		months = []
		for month_num in range(1, 13):
			# calendar.month_abbr[month_num] возвращает сокращенное название
			months.append(calendar.month_abbr[month_num].capitalize())

		return months
	except locale.Error:
		# Fallback на русские сокращения если локаль не доступна
		return ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
