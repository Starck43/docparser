import json
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from app.config import settings
from app.crud import get_documents, get_documents_with_errors, get_documents_count, delete_all_documents
from app.db import get_db
from app.services.export import export_to_xls_with_months
from app.services.files import display_files_tree
from app.services.parser import main_file_parser
from app.utils.base import get_current_year
from app.utils.console import confirm_prompt, console, print_error

app = typer.Typer(help="📄 CLI для парсинга документов")


@app.command()
def parse(
		data_dir: Optional[Path] = typer.Option(None, help="Папка с документами"),
		year: Optional[int] = typer.Option(None, help="Год для фильтрации"),
		limit: int = typer.Option(settings.MAX_FILES_TO_PROCESS, help="Лимит файлов для обработки (0 = все)"),
		dry_run: bool = typer.Option(False, help="Тестовый режим без сохранения в БД"),
		batch_size: int = typer.Option(
			settings.CONSOLE_OUTPUT_BATCH_SIZE,
			help="Количество документов для отображения в консоли"
		)
):
	"""Парсит документы из указанной папки"""

	files = display_files_tree(data_dir, max_display=batch_size)

	if confirm_prompt("Продолжить парсинг?", default=True):
		documents = main_file_parser(files[:limit], year, not dry_run, batch_size)
		console.print(f"✅ Обработано документов: {len(documents)}", style="green")


@app.command()
def export(
		year: Optional[int] = typer.Option(None, help="Год для экспорта"),
		output_dir: Optional[Path] = typer.Option(None, help="Папка для экспорта"),
		limit: int = typer.Option(0, help="Лимит документов для экспорта"),
		dry_run: bool = typer.Option(False, "--dry-run", help="Предпросмотр без сохранения"),
		max_per_file: int = typer.Option(
			None,
			help=f"Максимум документов в файле (по умолчанию: {settings.MAX_DOCUMENTS_PER_EXPORT_FILE})"
		),
		force: bool = typer.Option(
			False,
			"--force",
			help="Принудительная перезапись существующих файлов"
		)
):
	"""Экспортирует данные в XLSX файл с возможностью разбивки на части"""

	target_year = year or get_current_year()
	max_per_file = max_per_file or settings.MAX_DOCUMENTS_PER_EXPORT_FILE

	with next(get_db()) as db:
		documents = get_documents(db, year=target_year, limit=limit or None)

		if not documents:
			print_error(f"Нет документов за {target_year} год")
			return

		# DRY-RUN РЕЖИМ
		if dry_run:
			from app.services.preview import preview_export_data
			console.print("** РЕЖИМ ПРЕДПРОСМОТРА **", style="bold yellow")
			preview_export_data(list(documents), target_year)
			return

		# РЕАЛЬНЫЙ ЭКСПОРТ (существующая логика)
		export_dir = output_dir or settings.EXPORT_DIR
		export_dir.mkdir(exist_ok=True)

		# Разбиваем на части если нужно (исправлено условие)
		if 0 < max_per_file < len(documents):
			console.print(f"📦 Разбиваем {len(documents)} документов на части по {max_per_file}", style="yellow")
			export_paths = []

			for i in range(0, len(documents), max_per_file):
				batch_docs = documents[i:i + max_per_file]
				part_num = i // max_per_file + 1
				postfix = f"-part{part_num:02d}"

				export_path = export_to_xls_with_months(
					list(batch_docs), target_year, export_dir, postfix, force
				)
				export_paths.append(export_path)
				console.print(f"✅ Часть {part_num}: {export_path.name}")

			console.print(f"📊 Всего создано файлов: {len(export_paths)}", style="green")
			return export_paths
		else:
			export_path = export_to_xls_with_months(list(documents), target_year, export_dir, "", force)
			console.print(f"✅ Экспорт завершен: {export_path}", style="green")
			return [export_path]


@app.command()
def errors(
		year: Optional[int] = typer.Option(None, help="Год для фильтрации"),
		limit: int = typer.Option(10, help="Лимит документов для показа")
):
	"""Показывает документы с ошибками валидации"""
	with next(get_db()) as db:
		error_docs = get_documents_with_errors(db, year=year, limit=limit)

		if not error_docs:
			console.print("✅ Нет документов с ошибками", style="green")
			return

		table = Table(title="📋 Документы с ошибками")
		table.add_column("Файл", style="cyan")
		table.add_column("Ошибки", style="red")

		for doc in error_docs:
			errors_list = json.loads(doc.validation_errors) if doc.validation_errors else []
			table.add_row(str(doc.file_path), "\n".join(errors_list))

		console.print(table)


@app.command()
def stats(
		year: Optional[int] = typer.Option(None, help="Год для статистики")
):
	"""Показывает статистику по документам"""
	with next(get_db()) as db:
		total = get_documents_count(db, year=year)
		with_errors = len(get_documents_with_errors(db, year=year))

		console.print(f"📊 Статистика документов:", style="bold")
		console.print(f"   Всего: {total}")
		console.print(f"   С ошибками: {with_errors}")
		console.print(f"   Без ошибок: {total - with_errors}")


@app.command()
def clear_db(
		confirm: bool = typer.Option(False, "--confirm", help="Подтверждение очистки")
):
	"""Очищает базу данных"""
	if not confirm:
		console.print("⚠️  Используйте --confirm для очистки БД", style="yellow")
		return

	with next(get_db()) as db:
		deleted_count = delete_all_documents(db)
		console.print(f"✅ Удалено документов: {deleted_count}", style="green")


if __name__ == "__main__":
	app()
