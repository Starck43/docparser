import json
from pathlib import Path
from typing import Optional

import typer
from sqlmodel import Session

from app.config import settings
from app.db import engine
from app.services.document_parser import parse_document_file
from app.services.utils import find_documents, safe_move_file
from . import crud, models

app = typer.Typer(help="Парсер документов с планами закупок")


if __name__ == "__main__":
	app()
