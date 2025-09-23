from pathlib import Path
from typing import Optional

import typer

from app.config import settings
from app.db import get_db
from app.services.export import export_to_xls_with_months
from app.services.files import display_files_tree
from app.services.parser import main_file_parser
from app.utils.base import format_string_list, parse_range_string, get_current_year
from app.utils.console import confirm_prompt, console, print_error, print_success, print_warning
from app.crud import (
	get_documents, get_documents_count, delete_all_documents, delete_documents_by_year, get_documents_with_errors
)

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
		'range_str': range_str,
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
		limit: int = typer.Option(None, help="Лимит файлов для обработки (0 = все)"),
		dry_run: bool = typer.Option(False, help="Тестовый режим без сохранения в БД"),
		batch_size: int = typer.Option(
			None,
			help=f"Количество документов для отображения в консоли (по умолчанию {settings.CONSOLE_OUTPUT_BATCH_SIZE})"
		),
		force_update: bool = typer.Option(
			False,
			help="Всегда перезаписывать существующие данные или пропускать (по умолчанию: пропускать)"
		)
):
	"""Парсит документы из указанной папки"""

	params = get_common_cli_params(year=year, limit=limit, batch_size=batch_size, force_update=force_update)

	files = display_files_tree(data_dir, max_display=params['batch_size'])
	if not files:
		return

	if dry_run:
		print_warning("*** РЕЖИМ БЕЗ СОХРАНЕНИЯ ***")

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
		range_str: str = typer.Option("1-10", "--range", help="Диапазон документов: 1-10, :20, all"),
):
	"""Просмотр сохраненных документов"""

	params = get_common_cli_params(year=year)

	with next(get_db()) as db:
		total_count = get_documents_count(db, year=params['year'])

		# Получаем документы по диапазону
		try:
			offset, limit = parse_range_string(range_str, total_count)
		except ValueError as e:
			print_error(str(e))
			return

		documents = get_documents(db, year=params['year'], skip=offset, limit=limit)

		if not documents:
			print_error(f"Нет документов за {params['year']} год")
			return

		from app.services.preview import preview_export_data
		console.print(f"Просмотр сохраненных данных за {params['year']} год", style="green")
		preview_export_data(list(documents), params['year'])


@app.command()
def export(
		output_dir: Optional[Path] = typer.Option(
			settings.EXPORT_DIR,
			help=f"Папка для экспорта (по умолчанию: {settings.EXPORT_DIR})"
		),
		year: Optional[int] = typer.Option(None, help="Год для экспорта"),
		range_str: str = typer.Option("all", '--range', help="Диапазон: all, 1-100, 50-, 0:100, :200, 100:"),
		dry_run: bool = typer.Option(False, help="Предпросмотр без экспорта данных"),
		rows_per_file: int = typer.Option(
			0,
			help=f"Максимум строк в одном файле (0 - все в одном файле)"
		),
		force_update: bool = typer.Option(
			False,
			help="Принудительная перезапись существующих файлов (по умолчанию: не перезаписывать и создавать новый)"
		)
):
	"""Экспортирует данные в XLSX файл с возможностью разбивки на части"""

	params = get_common_cli_params(
		year=year,
		range_str=range_str,
		rows_per_file=rows_per_file,
		force_update=force_update
	)

	with next(get_db()) as db:
		if not params['range_str']:
			documents = get_documents(db, params['year'])

		else:
			# ⚡ Парсим диапазон в offset/limit
			total_count = get_documents_count(db, year=params['year'])
			offset, limit = parse_range_string(params['range_str'], total_count)

			# ⚡ Используем существующую функцию с offset/limit
			documents = get_documents(db, year=params['year'], skip=offset, limit=limit)

		if not documents:
			range_message = f"в диапазоне: {offset}-{limit}" if params["range_str"] else ""
			print_error(f"Не найдено документов за {params['year']} год {range_message}")
			return

		# DRY-RUN РЕЖИМ
		if dry_run:
			from app.services.preview import preview_export_data
			print_warning("*** РЕЖИМ ПРЕДПРОСМОТРА ***")
			preview_export_data(list(documents), params['year'])
			return

		# РЕАЛЬНЫЙ ЭКСПОРТ
		output_dir.mkdir(exist_ok=True)

		# Разбиваем на части если нужно
		if 0 < params['rows_per_file'] < len(documents):
			console.print(
				f"📦 Разбиваем {len(documents)} документов на части по {params['rows_per_file']}",
				style="yellow"
			)
			export_paths = []

			for i in range(0, len(documents), params['rows_per_file']):
				batch_docs = documents[i:i + params['rows_per_file']]
				part_num = i // params['rows_per_file'] + 1
				postfix = f"-part{part_num:02d}"

				export_path = export_to_xls_with_months(
					list(batch_docs),
					params['year'],
					output_dir,
					postfix,
					params['force_update']
				)
				export_paths.append(export_path)
				print_success(f"Часть {part_num}: {export_path.name}")

			print_success(f"Всего создано файлов: {len(export_paths)}")
			return export_paths
		else:
			export_path = export_to_xls_with_months(
				list(documents), params['year'], params['output_dir'], "", params['force']
			)

			console.print("\n" + "=" * 80, style="dim")
			print_success(f"Экспорт успешно завершен. Сохранено документов: {len(documents)}")
			console.print("📂 Ссылка на файл XLSX:", style="bold")
			console.print(f"📍 [link=file://{export_path}]{export_path}[/link]", style="blue underline")
			console.print("=" * 80, style="dim")

			return [export_path]


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

		from app.utils.console import print_table
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
		full_clean: bool = typer.Option(False, help="Подтверждение полной очистки всех данных"),
		confirm: bool = typer.Option(False, help="Подтверждение процедуры удаления без предупреждения")
):
	"""Очищает базу данных"""
	params = get_common_cli_params(year=year)

	msg = "полностью очистить базу данных" if full_clean else f"удалить данные за {params['year']} год"

	if not confirm or full_clean and confirm_prompt(f"❌ Вы уверены что хотите {msg}?", default=False):
		with next(get_db()) as db:
			if full_clean:
				deleted_count = delete_all_documents(db)
			else:
				deleted_count = delete_documents_by_year(db, params['year'])

			console.print(f"✅ Удалено документов: {deleted_count}")
	else:
		print_warning("Очистка отменена")


if __name__ == "__main__":
	app()
