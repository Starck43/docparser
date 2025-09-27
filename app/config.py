from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file='.env',
		env_file_encoding='utf-8',
		case_sensitive=False,
		extra='ignore',
	)

	# Paths
	BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
	DATA_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "data")
	EXPORT_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "export")

	# Database
	DATABASE_URL: str = "sqlite:///database.db"
	SQL_DEBUG_MODE: bool = False

	# File handling
	SUPPORTED_FORMATS: list[str] = [".docx", ".doc", ".pdf", ".txt"]
	BATCH_FLUSH_SIZE: int = 100
	MAX_FILES_TO_PROCESS: int = 0
	CONSOLE_OUTPUT_BATCH_SIZE: int = 5
	REWRITE_FILE_ON_CONFLICT: bool = False
	MAX_DOCUMENTS_PER_EXPORT_FILE: int = 200

	# Parsing
	EXCLUDE_NAME_LIST: list[str] = []
	LEGAL_ENTITY_PATTERNS: list[str] = [
		"ООО", "АО", "ОАО", "ПАО", "ИП",
		"Общество с ограниченной ответственностью",
		"Акционерное общество",
		"Публичное акционерное общество",
		"Индивидуальный предприниматель"
	]

	@classmethod
	def validate_paths(cls, data):
		path_fields = ['BASE_DIR', 'DATA_DIR', 'EXPORT_DIR']
		for field in path_fields:
			if field in data and isinstance(data[field], str):
				data[field] = Path(data[field])
		return data

	def __init__(self, **data):
		super().__init__(**data)
		self.DATA_DIR.mkdir(exist_ok=True)
		self.EXPORT_DIR.mkdir(exist_ok=True)


settings = Settings()
