import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterator, Any, TYPE_CHECKING, Optional

import docx
import pdfplumber

from app.config import settings

if TYPE_CHECKING:
	from app.models import Document


def is_supported(file: Path) -> bool:
	"""Проверить, что файл имеет поддерживаемое расширение"""
	return file.suffix.lower() in settings.SUPPORTED_FORMATS


def ensure_upload_dir() -> None:
	Path(settings.EXPORT_DIR).mkdir(parents=True, exist_ok=True)


def find_documents(directory: Path) -> Iterator[Path]:
	"""
	Находит все документы с указанными расширениями в директории.
	"""
	for ext in settings.SUPPORTED_FORMATS:
		yield from directory.glob(f'**/*{ext}')


def safe_move_file(src: Path, dst: Path) -> Path:
	"""
	Безопасно перемещает файл с созданием директорий и обработкой конфликтов.
	"""
	dst.parent.mkdir(parents=True, exist_ok=True)

	if dst.exists():
		if settings.AUTO_RENAME_ON_CONFLICT:
			counter = 1
			while dst.exists():
				new_name = f"{dst.stem}-{counter:02d}{dst.suffix}"
				dst = dst.with_name(new_name)
				counter += 1
		else:
			raise FileExistsError(f"Файл {dst} уже существует")

	shutil.move(str(src), str(dst))
	return dst


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


def parse_file_to_text(path: Path) -> str:
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


def clean_table_data(table: list[list[Any]]) -> list[list[str]]:
	"""
	Очищает данные таблицы: убирает переносы строк, None, выравнивает размеры.
	"""
	cleaned_table = []

	if not table:
		return cleaned_table

	# Находим максимальное количество колонок
	max_cols = max(len(row) for row in table) if table else 0

	for row in table:
		cleaned_row = []
		for cell in row:
			# Обрабатываем каждую ячейку
			if cell is None:
				cleaned_cell = ""
			else:
				# Заменяем переносы строк на пробелы и чистим
				cleaned_cell = str(cell).replace('\n', ' ').replace('\r', ' ')
				# Убираем лишние пробелы
				cleaned_cell = re.sub(r'\s+', ' ', cleaned_cell).strip()

			cleaned_row.append(cleaned_cell)

		# Добиваем строку до максимального количества колонок
		while len(cleaned_row) < max_cols:
			cleaned_row.append("")

		cleaned_table.append(cleaned_row)

	return cleaned_table


def document_to_document_create(doc: 'Document', customer_plans: dict[str, list[Optional[float]]]) -> 'DocumentCreate':
	"""
	Конвертирует Document в DocumentCreate для совместимости с print_monthly_summary.
	"""
	from app.models import DocumentCreate, ProductPlanCreate

	# Создаем планы из месячных данных
	plans = []
	for customer_name, monthly_plans in customer_plans.items():
		for month_idx, quantity in enumerate(monthly_plans, 1):
			if quantity is not None:
				plans.append(ProductPlanCreate(
					month=month_idx,
					year=doc.year,
					planned_quantity=quantity,
					customer_name=customer_name if customer_name != "Все покупатели" else None
				))

	return DocumentCreate(
		file_path=doc.file_path,
		agreement_number=doc.agreement_number,
		customer_names=json.loads(doc.customer_names) if doc.customer_names else [],
		year=doc.year,
		allowed_deviation=doc.allowed_deviation,
		validation_errors=json.loads(doc.validation_errors) if doc.validation_errors else [],
		plans=plans
	)


def print_formatted_table(table: list[list[Any]], title: str = "ТАБЛИЦА", max_col_width: int = 30):
	"""
	Отображает таблицу с ограничением ширины КАЖДОЙ колонки.
	Если ячейка превышает max_col_width - укорачивает с '...'
	"""
	if not table:
		print("   [пустая таблица]")
		return

	cleaned_table = clean_table_data(table)
	if not cleaned_table:
		return

	max_cols = len(cleaned_table[0])

	# 1. Определяем естественные ширины колонок (но не больше max_col_width)
	col_widths = [0] * max_cols
	for row in cleaned_table:
		for i, cell in enumerate(row):
			if i < max_cols:
				# Естественная ширина, но не больше ограничения
				cell_width = min(len(cell), max_col_width)
				col_widths[i] = max(col_widths[i], cell_width)

	# 2. Рассчитываем общую ширину таблицы
	total_width = sum(col_widths) + (max_cols - 1) * 3  # " │ " между колонками

	# 3. Отрисовываем таблицу
	print(f"   ┌{'─' * total_width}┐")
	print(f"   │ {title.center(total_width - 2)} │")
	print(f"   ├{'─' * total_width}┤")

	for row in cleaned_table:
		cells = []
		for i, cell in enumerate(row):
			if i < len(col_widths):
				display_cell = cell
				# Укорачиваем если превышает лимит
				if len(display_cell) > col_widths[i]:
					display_cell = display_cell[:col_widths[i] - 3] + "..."
				cells.append(display_cell.ljust(col_widths[i]))
			else:
				cells.append("")
		print(f"   │ {' │ '.join(cells)} │")

	print(f"   └{'─' * total_width}┘")


def print_monthly_summary(document_data: 'DocumentCreate'):
	"""
	Отображает сводку планов закупок с учетом допустимого отклонения.
	"""

	# Группируем планы по покупателям
	plans_by_customer = {}
	for plan in document_data.plans:
		customer_key = plan.customer_name or "all"
		if customer_key not in plans_by_customer:
			plans_by_customer[customer_key] = [None] * 12

		if 1 <= plan.month <= 12 and plan.planned_quantity is not None:
			month_index = plan.month - 1
			# инициализируем и суммируем
			if plans_by_customer[customer_key][month_index] is None:
				plans_by_customer[customer_key][month_index] = plan.planned_quantity
			else:
				plans_by_customer[customer_key][month_index] += plan.planned_quantity

	# Отображаем для каждого покупателя
	for customer_name, monthly_plans in plans_by_customer.items():
		display_name = "" if customer_name == "all" else customer_name

		# Помечаем неизвестных покупателей
		if customer_name.startswith('*'):
			display_name = f"⚠️  {customer_name}"

		if display_name:
			print(f"\n   👥 {display_name}:")

		# Создаем таблицу
		table_data = [
			["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек", "Итого"]
		]

		row = []
		total = 0
		for monthly_plan in monthly_plans:
			if monthly_plan is not None:
				row.append(str(monthly_plan))
				total += monthly_plan
			else:
				row.append("")

		row.append(str(total))
		table_data.append(row)

		print_formatted_table(table_data, "СУММАРНЫЕ ПЛАНЫ", max_col_width=8)


def get_current_year() -> int:
	"""
	Возвращает текущий год.
	Используется как значение по умолчанию при парсинге.
	"""
	return datetime.now().year


def get_unique_filename(directory: Path, base_name: str, extension: str = ".xlsx") -> Path:
	"""
	Генерирует уникальное имя файла, добавляя индекс если файл уже существует.

	Args:
		directory: Папка для сохранения
		base_name: Базовое имя файла (без расширения)
		extension: Расширение файла (по умолчанию .xlsx)

	Returns:
		Путь к уникальному файлу
	"""
	counter = 1
	while True:
		if counter == 1:
			filename = f"{base_name}{extension}"
		else:
			filename = f"{base_name}-{counter:02d}{extension}"

		file_path = directory / filename

		if not file_path.exists():
			return file_path

		# Предлагаем пользователю выбрать действие
		choice = input(
			f"Файл {filename} уже существует. (д - Перезаписать,  другая клавиша - Сохранить под новым именем): "
		).lower().strip()
		if choice in ['д', 'да', 'у', 'y', 'yes']:
			return file_path
		else:
			counter += 1
