from pathlib import Path
from typing import Optional

import typer

from app.config import settings
from app.crud import (
	get_documents_count, delete_all_documents, delete_documents_by_year, get_documents_with_errors
)
from app.db import get_db
from app.services.export import export_documents_to_file
from app.services.files import display_files_tree
from app.services.parser import main_file_parser
from app.services.preview import paginated_preview, preview_documents_details
from app.utils.base import format_string_list, parse_range_string, get_current_year
from app.utils.console import confirm_prompt, console, print_error, print_success, print_warning, print_table

app = typer.Typer(help="📄 CLI команды для гибкой работы с данными")


def get_common_cli_params(
		range_str: Optional[str] = None,
		year: Optional[int] = None,
		limit: int = 0,
		batch_size: int = None,
		rows_per_file: int = settings.MAX_DOCUMENTS_PER_EXPORT_FILE,
		force_update: bool = False,
		full_clean: bool = False
):
	"""Общие параметры для парсинга"""
	return {
		'year': year or get_current_year(),
		'range_str': range_str or settings.MAX_FILES_TO_PROCESS or 'all',
		'limit': limit or settings.MAX_FILES_TO_PROCESS,
		'batch_size': batch_size or settings.CONSOLE_OUTPUT_BATCH_SIZE,
		'rows_per_file': rows_per_file or settings.MAX_DOCUMENTS_PER_EXPORT_FILE,
		'force_update': force_update or settings.REWRITE_FILE_ON_CONFLICT,
		'full_clean': full_clean
	}


@app.command()
def parse(
		data_dir: Optional[Path] = typer.Option(
			settings.DATA_DIR,
			help=f"Папка с исходными документами (по умолчанию: {settings.DATA_DIR})"
		),
		year: Optional[int] = typer.Option(None, help="Год для выборки данных (по умолчанию: текущий)"),
		limit: int = typer.Option(
			None,
			help=f"Лимит файлов для обработки (по умолчанию: {settings.MAX_FILES_TO_PROCESS or 'нет'})"
		),
		dry_run: bool = typer.Option(False, help="Тестовый режим без сохранения в БД"),
		batch_size: int = typer.Option(
			None,
			help=f"Количество документов для отображения в консоли (по умолчанию: {settings.CONSOLE_OUTPUT_BATCH_SIZE})"
		),
		force_update: bool = typer.Option(
			False,
			help=(
					f"Всегда перезаписывать существующие данные или пропускать "
					f"(по умолчанию: {'' if settings.REWRITE_FILE_ON_CONFLICT else 'не '}перезаписывать)"
			)
		)
):
	"""Парсит документы из указанной папки"""

	params = get_common_cli_params(year=year, limit=limit, batch_size=batch_size, force_update=force_update)

	files = display_files_tree(data_dir, max_display=params['batch_size'])
	if not files:
		return

	if dry_run:
		print_warning("*** РЕЖИМ ПАРСИНГА БЕЗ СОХРАНЕНИЯ В БД ***")

	if confirm_prompt("Продолжить парсинг?", default=True):
		main_file_parser(
			files[:params['limit'] or None],
			params['year'],
			not dry_run,
			update_mode=params['force_update'],
			use_bulk=True
		)


@app.command()
def preview(
		year: Optional[int] = typer.Option(None, help="Год для просмотра (по умолчанию: текущий)"),
		range_str: str = typer.Option(
			None,
			"--range",
			help=f"Диапазон: 1-100, 50-, 0:100, :200, 100: (по умолчанию: {settings.MAX_FILES_TO_PROCESS or 'нет'})"
		),
		batch_size: int = typer.Option(
			None,
			help=f"Количество документов для отображения в консоли (по умолчанию: {settings.CONSOLE_OUTPUT_BATCH_SIZE})"
		),

):
	"""Просмотр сохраненных документов"""

	params = get_common_cli_params(range_str, year=year, batch_size=batch_size)

	try:
		offset, limit = parse_range_string(params['range_str'])
	except ValueError as e:
		print_error(str(e))
		return

	paginated_preview(
		title=f" Детальный просмотр сохраненных документов за {params['year']}",
		func=preview_documents_details,
		batch_size=params['batch_size'],
		year=params['year'],
		skip=offset,
		limit=limit,
	)


@app.command()
def export(
		output_dir: Optional[Path] = typer.Option(
			settings.EXPORT_DIR,
			help=f"Папка для экспорта (по умолчанию: {settings.EXPORT_DIR})"
		),
		year: Optional[int] = typer.Option(None, help="Год для экспортных данных (по умолчанию: текущий)"),
		range_str: str = typer.Option(
			None,
			'--range',
			help=f"Диапазон: 1-100, 50-, 0:100, :200, 100: (по умолчанию: {settings.MAX_FILES_TO_PROCESS or 'нет'})"
		),
		dry_run: bool = typer.Option(False, help="Предпросмотр без экспорта данных"),
		rows_per_file: int = typer.Option(
			0,
			help=(
					f"Лимит сохраняемых строк в одном файле "
					f"(по умолчанию: {settings.MAX_DOCUMENTS_PER_EXPORT_FILE or 'без ограничения'})"
			)
		),
		force_update: bool = typer.Option(
			False,
			help=(
					f"Принудительная перезапись существующих файлов "
					f"(по умолчанию: {'' if settings.REWRITE_FILE_ON_CONFLICT else 'не '}перезаписывать)"
			)
		)
):
	"""Экспортирует данные в XLSX файл с возможностью разбивки на части"""

	params = get_common_cli_params(
		year=year,
		range_str=range_str,
		rows_per_file=rows_per_file,
		force_update=force_update
	)

	year = params['year']
	range_str = params["range_str"]
	rows_per_file = params['rows_per_file']

	try:
		offset, limit = parse_range_string(range_str)

	except ValueError as e:
		print_error(str(e))
		return

	# DRY-RUN РЕЖИМ ПРОСМОТРА
	if dry_run:
		from app.services.preview import preview_summary_plans_list
		print_warning("*** РЕЖИМ ПРЕДПРОСМОТРА ***")

		paginated_preview(
			title=f"Просмотр помесячных планов закупок за {year} год",
			func=preview_summary_plans_list,
			year=year,
			skip=offset,
			limit=limit,
		)
		return

	# РЕАЛЬНЫЙ ЭКСПОРТ
	export_documents_to_file(
		title=f"Экспорт помесячных планов закупок за {year} год",
		year=year,
		output_dir=output_dir,
		rows_per_file=rows_per_file,
		force_update=params['force_update'],
		offset=offset,
		limit=limit,
	)


@app.command()
def errors(
		year: Optional[int] = typer.Option(None, help="Год для поиска ошибок (по умолчанию: текущий)"),
):
	"""Показывает документы с ошибками валидации"""
	params = get_common_cli_params(year=year)

	with next(get_db()) as db:
		error_docs = get_documents_with_errors(db, year=params['year'])

		if not error_docs:
			print_success("Ошибки не обнаружены!")
			return

		table = print_table("📋 Документы с ошибками", Файл="cyan", Ошибки="red")

		for doc in error_docs:
			errors_text = format_string_list(doc.validation_errors)
			table.add_row(str(doc.file_path), errors_text)

		console.print(table)


@app.command()
def stats(
		year: Optional[int] = typer.Option(None, help="Год для получения статистики (по умолчанию: текущий)")
):
	"""Показывает статистику по документам"""
	params = get_common_cli_params(year=year)

	with next(get_db()) as db:
		total = get_documents_count(db, year=params['year'])
		with_errors = len(get_documents_with_errors(db, year=params['year']))

		console.print(f"📊 Статистика документов за {params['year']} год:", style="bold")
		console.print(f"   Всего: {total}")
		console.print(f"   С ошибками: {with_errors}")


@app.command()
def clean(
		year: Optional[int] = typer.Option(None, help="Год для очистки данных (по умолчанию: текущий)"),
		full_clean: bool = typer.Option(False, help="Полная очистка всех данных за все годы (по умолчанию: спросить)"),
		no_confirm: bool = typer.Option(False, "--no-confirm", help="Не спрашивать подтверждение перед удалением")
):
	"""
	Очищает базу данных.
	По умолчанию запрашивает подтверждение перед удалением.
	"""
	params = get_common_cli_params(year=year)

	# Определяем сообщение для подтверждения
	if full_clean:
		msg = (
			"❌ ВНИМАНИЕ! Вы собираетесь полностью очистить базу данных.\n"
			"Все документы и связанные таблицы будут удалены.\n"
			"Вы уверены, что хотите продолжить?"
		)
	else:
		msg = f"❌ Вы уверены, что хотите удалить данные за {params['year']} год?"

	# Запрашиваем подтверждение, если не отключено
	if no_confirm or confirm_prompt(msg, default=False):
		with next(get_db()) as db:
			if full_clean:
				deleted_count = delete_all_documents(db)
				console.print(f"✅ Удалено документов: {deleted_count}")
			else:
				deleted_count = delete_documents_by_year(db, params['year'])
				console.print(f"✅ Удалено документов за {params['year']} год: {deleted_count}")
	else:
		print_warning("❌ Операция отменена пользователем")


if __name__ == "__main__":
	app()
