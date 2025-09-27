import os
from pathlib import Path
from typing import Tuple, List

from app.config import settings
from app.utils.base import is_supported

from app.utils.console import confirm_prompt


def get_export_file_path(
		directory: Path,
		base_name: str,
		postfix: str = "",
		extension: str = ".xlsx"
) -> Tuple[Path, List[Path]]:
	"""
	Возвращает путь для экспорта и список существующих part-файлов.
	
	Args:
		directory: Директория для поиска файлов
		base_name: Базовое имя файла
		postfix: Постфикс для имени файла
		extension: Расширение файла
		
	Returns:
		Кортеж из (основной_путь, список_частей)
	"""
	base_name = f"{base_name}{postfix}"
	file_path = directory / f"{base_name}{extension}"

	# Создаем паттерн для поиска всех файлов с тем же базовым именем и расширением,
	# но с дополнительным суффиксом-цифрой (например, -1, -2, -part1, -part2 и т.д.)
	pattern = f"{base_name}-*[0-9]*{extension}"
	part_files = [f for f in directory.glob(pattern) if f != file_path]

	return file_path, part_files


def cleanup_existing_files(file_path: Path, part_files: List[Path], force_overwrite: bool) -> None:
	"""Удаляет существующие файлы, если force_overwrite=True."""
	if not force_overwrite:
		return

	# Удаляем основной файл, если существует
	if file_path.exists():
		os.remove(file_path)

	# Удаляем все part-файлы
	for part_file in part_files:
		if part_file.exists():
			os.remove(part_file)


def get_unique_filename(
		directory: Path,
		base_name: str,
		postfix: str = "",
		extension: str = ".xlsx",
		skip_if_exists: bool = False
) -> Path:
	"""
	Генерирует уникальное имя файла, добавляя индекс если файл уже существует.

	Args:
		directory: Папка для сохранения
		base_name: Базовое имя файла (без расширения)
		extension: Расширение файла (по умолчанию .xlsx)
		postfix: Дополнительное окончание к имени файла
		skip_if_exists: Пропускать проверку существования файла

	Returns:
		Путь к уникальному файлу
	"""
	# Если skip_if_exists=True, просто возвращаем путь без проверок
	if skip_if_exists:
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

		counter += 1


def find_files(directory: Path) -> list[Path]:
	"""Находит и возвращает все файлы поддерживаемых форматов"""
	files: list[Path] = []

	for ext in settings.SUPPORTED_FORMATS:
		files.extend(directory.glob(f"**/*{ext}"))

	# Фильтрация и сортировка для стабильного результата
	return sorted([f for f in files if is_supported(f)])
