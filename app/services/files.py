from pathlib import Path
from typing import TYPE_CHECKING

from app.config import settings
from app.utils.base import is_supported
from app.utils.console import print_success, print_error, console


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


def display_files_tree(source: Path, max_display: int = settings.CONSOLE_OUTPUT_BATCH_SIZE) -> list[Path]:
	"""Отображает дерево файлов и возвращает список найденных файлов"""
	files = find_files(source)

	if not files:
		print_error("Файлы не найдены")
		return []

	console.print(f"\n📁 {source.name.upper()}/", style="bold")
	for i, file in enumerate(files[:max_display], 1):
		console.print(f"├── 📄 [gray]{file.name}[/gray]")

	if len(files) > max_display:
		console.print(f"└── ... и еще [gray]{len(files) - max_display}[/gray] файлов")

	print_success(f"Обнаружено файлов: [cyan]{len(files)}[/cyan]\n")
	return files
