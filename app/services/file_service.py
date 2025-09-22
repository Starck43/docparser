from pathlib import Path
from typing import Optional, TYPE_CHECKING
from app.config import settings
from app.crud import save_document
from app.db import get_db
from app.services.document_parser import DocumentParser
from app.utils.base import is_supported

if TYPE_CHECKING:
	from app.models import DocumentCreate


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


def parse_files(
		files: list[Path],
		year: Optional[int] = None,
		save_to_db: bool = True,
		batch_size: int = 5
) -> list['DocumentCreate']:
	"""
	Парсит файлы используя существующий DocumentParser
	"""
	parser = DocumentParser()
	documents = []
	processed = 0

	for i, file_path in enumerate(files, 1):
		try:
			# Парсим документ
			document = parser.parse_document(file_path)

			# Проверяем год если указан
			if year is not None and document.year != year:
				continue

			# Сохраняем в БД если нужно
			if save_to_db:
				with next(get_db()) as db:
					save_document(db, document)

			documents.append(document)
			processed += 1

			# Показываем прогресс для batch_size
			if processed <= batch_size:
				print(f"📋 [{i}/{len(files)}] Обработан: {file_path.name}")
				if hasattr(document, 'agreement_number') and document.agreement_number:
					print(f"   📄 Договор: {document.agreement_number}")

		except Exception as e:
			print(f"❌ Ошибка обработки {file_path.name}: {e}")
			continue

	if processed > batch_size:
		print(f"📊 ... пропущено {processed - batch_size} документов")

	return documents
