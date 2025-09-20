import shutil
from pathlib import Path
from typing import Iterator

import docx
from PyPDF2 import PdfReader

from app.config import settings


def is_supported(file: Path) -> bool:
	"""Проверить, что файл имеет поддерживаемое расширение"""
	return file.suffix.lower() in settings.SUPPORTED_FORMATS


def ensure_upload_dir() -> None:
	Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


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


def extract_text_from_txt(path: str) -> str:
	"""
	Извлечение текста средствами Python.
	"""
	with open(path, "r", encoding="utf-8", errors="ignore") as f:
		return f.read()


def extract_text_from_docx(path: str) -> str:
	"""
	Извлечение текста средствами docx.
	"""
	doc = docx.Document(path)
	return "\n".join(p.text for p in doc.paragraphs)


def extract_text_from_pdf(path: str) -> str:
	"""
	Извлечение текста средствами PyPDF2.
	"""
	texts = []
	reader = PdfReader(path)
	for page in reader.pages:
		page_text = page.extract_text()
		if page_text:
			texts.append(page_text)
	return "\n".join(texts).strip()


def parse_file_to_text(path: Path) -> str:
	"""
	Универсальный парсер: выбирает логику по расширению.
	Возвращает извлечённый текст (может быть пустой строкой).
	"""
	if not is_supported(path):
		raise ValueError(f"Формат {path.suffix} не поддерживается")

	suffix = path.suffix.lower()
	path_str = str(path)

	if suffix in {".txt"}:
		return extract_text_from_txt(path_str)
	if suffix in {".docx", ".doc"}:
		return extract_text_from_docx(path_str)
	if suffix in {".pdf"}:
		return extract_text_from_pdf(path_str)

	# неизвестный формат — попытка прочитать как текст
	try:
		return extract_text_from_txt(path_str)
	except Exception:
		return ""
