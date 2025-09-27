from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.base import get_current_year, is_supported
from app.utils.console import print_success, print_error, console
from app.utils.tables import extract_from_pdf, extract_from_docx, extract_from_txt


def display_files_tree(
		files: list[Path],
		max_display: int = settings.CONSOLE_OUTPUT_BATCH_SIZE,
		offset: int = 0,
		limit: int | None = None,
) -> list[Path]:
	"""Отображает дерево файлов и возвращает список найденных файлов"""

	if not files:
		print_error("Файлы не найдены")
		return []

	# Применяем диапазон
	if limit is None:
		selected = files[offset:]
	else:
		selected = files[offset:offset + limit]

	console.print(f"\n📁 {files[0].parent.name.upper()}/", style="bold")
	for i, file in enumerate(selected[:max_display], 1):
		console.print(f"├── 📄 [gray]{file.name}[/gray]")

	if len(selected) > max_display:
		console.print(f"└── ... и еще [gray]{len(selected) - max_display}[/gray] файлов")

	print_success(f"Обнаружено файлов для обработки: [cyan]{len(selected)}[/cyan]\n")
	return selected


def convert_file_to_text(file_path: Path, year: int = None) -> tuple[str, Optional[list[list[list[str]]]]]:
	"""
	Извлекает текст и таблицы из файла, фильтрует по году и приводит к виду:
	[[MM.YYYY, сумма], ...]

	Args:
		file_path: Путь к файлу
		year: Год для фильтрации строк

	Returns:
		tuple:
			- text_content (str): весь текст документа
			- results (list[list[str]] | None): список рядов вида [дата, сумма]
	"""
	if not file_path.exists():
		print(f"Файл не найден: {file_path} [игнорируем]")
		return "", None

	if not is_supported(file_path):
		print(f"Неподдерживаемый формат файла: {file_path} [игнорируем]")
		return "", None

	file_ext = file_path.suffix.lower()

	if not year:
		year = get_current_year()

	try:
		if file_ext == ".pdf":
			return extract_from_pdf(file_path, year)
		elif file_ext in [".docx", ".doc"]:
			return extract_from_docx(file_path, year)
		elif file_ext == ".txt":
			return extract_from_txt(file_path, year)
		else:
			raise ValueError(f"Неподдерживаемый формат файла: {file_ext}")
	except Exception as e:
		raise Exception(f"Ошибка извлечения данных из {file_path.name}: {e}")
