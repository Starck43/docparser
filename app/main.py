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


def _print_document_info(document_data: models.DocumentCreate):
	"""Выводит информацию о распарсенном документе."""
	typer.echo(f"\n📄 {document_data.agreement_number or 'Без номера'}")
	if document_data.customer_name:
		typer.echo(f"   👥 {document_data.customer_name}")

	if document_data.plans:
		typer.echo(f"   📊 Планов: {len(document_data.plans)}")

	if document_data.validation_errors:
		typer.echo(f"   ⚠️  Ошибки: {len(document_data.validation_errors)}")


@app.command()
def parse_folder(
		folder_path: Path = typer.Argument(settings.DATA_DIR, help="Путь к папке с документами"),
		output_dir: Path = typer.Option(settings.OUTPUT_DIR, help="Папка для обработанных документов"),
		max_files: int = typer.Option(settings.MAX_FILES_TO_PROCESS, help="Максимальное количество файлов для обработки")
):
	"""
	Парсит все документы в указанной папке.
	"""
	with Session(engine) as db:
		files_processed = 0
		for file_path in find_documents(folder_path):
			if settings.MAX_FILES_TO_PROCESS and files_processed >= max_files:
				break

			try:
				# Парсим документ
				document_data = parse_document_file(file_path)
				if not document_data:
					typer.echo(f"Не удалось распарсить: {file_path.name}")
					continue

				# Сохраняем в БД
				existing = crud.get_document_by_file_path(db, str(file_path))
				if existing:
					typer.echo(f"Документ {file_path.name} уже обработан")
					continue

				crud.create_document(db, document_data)

				# Перемещаем в папку обработанных
				if output_dir:
					new_path = safe_move_file(file_path, output_dir / file_path.name)
					typer.echo(f"Обработан: {file_path.name} -> {new_path.name}")

				# Выводим информацию о документе
				_print_document_info(document_data)

				files_processed += 1

			except Exception as e:
				typer.echo(f"Ошибка обработки {file_path}: {e}", err=True)


@app.command()
def show_documents(
		year: Optional[int] = typer.Option(None, help="Фильтр по году"),
		limit: int = typer.Option(settings.CONSOLE_OUTPUT_BATCH_SIZE, help="Количество записей"),
		skip: int = typer.Option(0, help="Пропустить первые N записей")
):
	"""
	Показывает документы с фильтром по году.
	"""
	with Session(engine) as db:
		documents = crud.get_documents_with_plans(db, year=year, skip=skip, limit=limit)

		for doc in documents:
			customers = json.loads(doc.customer_names) if doc.customer_names else []
			customer_str = " и ".join(customers) if customers else "Неизвестный покупатель"
			typer.echo(f"\n{doc.agreement_number or 'Без номера'} ({doc.year}): {customer_str}")

			for plan in doc.plans:
				typer.echo(f"  {plan.month:02d}.{plan.year}: {plan.planned_quantity} т - {plan.product_name}")


if __name__ == "__main__":
	app()
