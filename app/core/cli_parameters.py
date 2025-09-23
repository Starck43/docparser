from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.base import get_current_year


def get_common_cli_params(
		range_str: Optional[str] = None,
		year: Optional[int] = None,
		limit: int = 0,
		batch_size: int = 10,
		rows_per_file: int = settings.MAX_DOCUMENTS_PER_EXPORT_FILE,
		force_update: bool = False,
		full_clean: bool = False
):
	"""Общие параметры для парсинга"""
	return {
		'year': year or get_current_year(),
		'range_str': range_str,
		'limit': limit or settings.MAX_FILES_TO_PROCESS,
		'batch_size': batch_size or settings.CONSOLE_OUTPUT_BATCH_SIZE,
		'rows_per_file': rows_per_file or settings.MAX_DOCUMENTS_PER_EXPORT_FILE,
		'force_update': force_update or settings.REWRITE_FILE_ON_CONFLICT,
		'full_clean': full_clean
	}
