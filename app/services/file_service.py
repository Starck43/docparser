from pathlib import Path
from typing import Optional
from app.config import settings
from app.utils.base import is_supported


def find_files(data_dir: Optional[Path] = None, limit: int = 0) -> list[Path]:
	"""Находит файлы в указанной директории с поддержкой форматов"""
	directory = data_dir or settings.DATA_DIR
	files = []

	for ext in settings.SUPPORTED_FORMATS:
		pattern = f"**/*{ext}"
		found = list(directory.glob(pattern))
		files.extend(found)

	files = [f for f in files if is_supported(f)]

	if limit > 0:
		return files[:limit]
	return files


def display_files_tree(files: list[Path], max_display: int = 5) -> None:
	"""Отображает дерево файлов"""
	if not files:
		print("Файлы не найдены")
		return

	print(f"📁 Папка: {files[0].parent}")
	print("├── 📄 " + files[0].name)

	for i, file in enumerate(files[1:max_display], 1):
		print("├── 📄 " + file.name)

	if len(files) > max_display:
		print(f"└── ... и еще {len(files) - max_display} файлов")
