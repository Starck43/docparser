from pathlib import Path
from typing import Optional, TYPE_CHECKING

from app.config import settings
from app.crud import save_document
from app.db import get_db
from app.services.document_parser import DocumentParser
from app.utils.base import is_supported
from app.utils.cli_utils import print_warning, print_success, print_error, console

if TYPE_CHECKING:
	from app.models import Document


def find_files(directory: Path, limit: int = 0) -> list[Path]:
	"""Находит файлы в указанной директории с поддержкой форматов"""
	files = []

	for ext in settings.SUPPORTED_FORMATS:
		pattern = f"**/*{ext}"
		found = list(directory.glob(pattern))
		files.extend(found)

	files = [f for f in files if is_supported(f)]

	if limit > 0:
		return files[:limit]
	return files


def display_files_tree(source: Path, max_display: int = 10) -> list[Path]:
	"""Отображает дерево файлов и возвращает список найденных файлов"""
	files = find_files(source)

	if not files:
		print_error("Файлы не найдены")
		return []

	console.print(f"\n📁 {source.name.upper()}/", style="bold")
	for i, file in enumerate(files[:max_display], 1):
		prefix = "├──" if i < len(files) and i < max_display else "└──"
		console.print(f"{prefix} 📄 [cyan]{file.name}[cyan]")

	if len(files) > max_display:
		console.print(f"└── ... и еще [cyan]{len(files) - max_display}[/cyan] файлов")

	print_success(f"Обнаружено файлов: [cyan]{len(files)}[/cyan]\n")
	return files


def parse_files(
		files: list[Path],
		year: Optional[int] = None,
		save_to_db: bool = True,
		batch_size: int = settings.CONSOLE_OUTPUT_BATCH_SIZE
) -> list['Document']:
	"""Парсит файлы используя существующий DocumentParser."""
	parser = DocumentParser()
	documents = []
	processed = 0

	for i, file_path in enumerate(files, 1):
		try:
			# Парсим документ
			document = parser.parse_document(file_path)

			# Проверяем год если указан
			if year is not None and document.year != year:
				print_warning(f"Пропущен документ {file_path.name} (год в документе: {document.year})")
				continue

			# Сохраняем в БД если нужно
			if save_to_db:
				with next(get_db()) as db:
					document = save_document(db, document)

			documents.append(document)
			processed += 1

			# Формируем базовую информацию о файле
			info_text = f"[{i}/{len(files)}]: {file_path.name}"

			# Проверяем наличие ошибок валидации
			has_errors = bool(document.validation_errors)
			status_text = "[red]ERR[/red]" if has_errors else "[green]OK[/green]"

			# Дополнительная информация об ошибках
			error_info = ""
			if has_errors:
				error_count = len(document.validation_errors)
				error_info = f" ([orange]{error_count} ошибок[/orange])"

			# Показываем прогресс для всех файлов с ошибками или первых N
			if has_errors or processed <= batch_size:
				console.print(f"{info_text} ... {status_text}{error_info}")

				# Показываем ошибки если есть
				if has_errors:
					for error in document.validation_errors:
						console.print(f"   ⚠️  [yellow]{error}[/yellow]")

			# Показываем последний файл если были пропуски
			elif i == len(files) and processed > batch_size:
				console.print(f"📊 ... + еще {processed - batch_size} файлов обработано")
				console.print(f"{info_text} ... {status_text}{error_info}")

		except Exception as e:
			print_error(f"Ошибка обработки {file_path.name}: {e}")
			continue

	return documents
