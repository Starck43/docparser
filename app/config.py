from pydantic import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./docparser.db"
    UPLOAD_DIR: str = "uploads"
    SUPPORTED_FORMATS = [".docx", ".doc", ".pdf", ".txt"]

