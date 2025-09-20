from pathlib import Path
from ..config import Settings

settings = Settings()


def is_supported(file: Path) -> bool:
	"""Проверить, что файл имеет поддерживаемое расширение"""
	return file.suffix.lower() in settings.SUPPORTED_FORMATS


def ensure_upload_dir() -> None:
	Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
