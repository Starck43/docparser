from pathlib import Path
from typing import TYPE_CHECKING, Callable, Any

from rich.progress import Progress, TextColumn, BarColumn
from rich.table import Table

from app.config import settings
from app.crud import get_documents_count, get_documents_with_grouped_plans
from app.db import get_db
from app.utils.base import format_string_list, get_localized_months_list, get_current_year
from app.utils.console import console

if TYPE_CHECKING:
	from app.models import DocumentCreate


def paginated_preview(
		func: Callable[[list[Any], int, int], None],
		title: str = "Просмотр данных",
		**kwargs: Any,
) -> None:
	"""
	Универсальная оболочка для постраничного просмотра с подгрузкой из БД.
	Args:
		func: Callable[[list[Any], int, int], None]
		title: Заголовок
		**kwargs:  'year', 'skip', 'limit', batch_size
	"""
	year = kwargs.get('year') or get_current_year()
	offset = kwargs.get('skip') or 0
	limit = kwargs.get('limit')
	batch_size = kwargs.get('batch_size') or settings.CONSOLE_OUTPUT_BATCH_SIZE

	total_errors = 0

	console.print("=" * len(title), style="blue")
	console.print(title.upper(), style="bold blue")
	if limit is not None or offset > 0:
		console.print(f"🎯 в диапазоне: [italic cyan]{offset+1}-{offset + limit}[/italic cyan]")
	console.print("=" * len(title), style="blue")

	with next(get_db()) as db, Progress(
			TextColumn("[progress.description]{task.description}"),
			BarColumn(),
			TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
			TextColumn("({task.completed}/{task.total})"),
			console=console,
			transient=True
	) as progress:

		# Получаем общее количество документов в БД
		total_in_db = get_documents_count(db, year=year)

		# Вычисляем реальный диапазон для показа
		if limit is not None:
			# Для диапазона 2-9: offset=1, limit=8, total_count=min(1+8, 10)=9
			total_count = min(offset + limit, total_in_db)
			docs_to_show = total_count - offset  # 9-1=8 документов нужно показать
		else:
			total_count = total_in_db
			docs_to_show = total_count - offset

		if docs_to_show <= 0:
			console.print("❌ Нет документов для отображения в указанном диапазоне", style="red")
			return

		progress_title = "💡 [bold red]Ctrl+C[/bold red] - прервать."
		task = progress.add_task(f"{progress_title}", total=docs_to_show)

		current_index = offset
		docs_processed = 0

		# Основной цикл пагинации
		while current_index < total_count and docs_processed < docs_to_show:
			remaining = docs_to_show - docs_processed
			current_batch_size = min(batch_size, remaining)

			batch_docs = get_documents_with_grouped_plans(
				db,
				year=year,
				skip=current_index,
				limit=current_batch_size
			)

			if not batch_docs:
				break

			# Подсчет ошибок
			batch_errors = sum(
				1 for doc_item in batch_docs
				if hasattr(
					doc_item[0] if isinstance(doc_item, tuple) else doc_item,
					'has_validation_errors'
				) and (
					doc_item[0] if isinstance(doc_item, tuple) else doc_item
				).has_validation_errors
			)
			total_errors += batch_errors

			func(list(batch_docs), current_index + 1, total_count)

			batch_len = len(batch_docs)
			current_index += batch_len
			docs_processed += batch_len
			progress.update(task, completed=docs_processed)

			if docs_processed < docs_to_show:
				try:
					input("💡 Нажмите [bold]Enter[/bold] для продолжения...")
				except KeyboardInterrupt:
					break

	if docs_processed >= docs_to_show:
		console.print("\n✅ Просмотр завершен.", style="bold green")
	else:
		console.print(f"\n🛑 Просмотр прерван. Не просмотрено: {docs_to_show - docs_processed}", style="yellow")

	console.print("=" * 40, style="dim")
	console.print(f"📁 Показано документов: [green]{docs_processed} / {total_in_db}[/green]")
	console.print(f"⚠️ С ошибками: [red]{total_errors}[/red]")
	console.print("=" * 40 + "\n", style="dim")


def preview_documents_details(documents: list, start_num: int = 1, limit: int = None):
	"""Детальный просмотр документов"""

	for i, doc in enumerate(documents, start_num):
		if isinstance(doc, tuple) and len(doc) == 2:
			# Формат (Document, summary)
			document, summary = doc
		else:
			# Формат Document
			document = doc
			summary = doc.get_plans_summary()

		title = f"\n📄 [{i}]: [bold white]{Path(document.file_path).name}[/bold white]"
		console.print(title)
		console.print("-" * (len(title) - 24), style="dim")

		# Основная информация
		console.print(f"   📋 Соглашение: {document.agreement_number or '<не установлено>'}")
		console.print(f"   📅 Действует до: [bold]{document.year}[/bold]")
		console.print(
			f"   👥 Контрагенты: "
			f"[green bold]"
			f"{format_string_list(document.customer_names_list, separator=' + ') or '—'}"
			f"[/green bold]"
		)
		console.print(
			f"   📏 Минимально допустимое отклонение: "
			f"[yellow bold]"
			f"{document.allowed_deviation or '—'}"
			f"[/yellow bold]"
		)

		# Группированные планы закупок по покупателям
		if summary:
			preview_document_plans(summary)
		else:
			console.print("   📊 Планы закупок: [yellow]нет данных[/yellow]")

		if document.has_validation_errors:
			console.print(f"   ❌ Ошибки: [red]{format_string_list(document.validation_errors_list)}[/red]")


def preview_summary_plans_list(documents: list, start_num: int = 1, limit: int = None) -> None:
	"""
	Показывает объединенные планы всех документов в одной таблице.
	"""
	if not documents:
		console.print("📭 Нет данных по плановым закупкам", style="yellow")
		return

	# Собираем все планы в одну структуру
	combined_plans = {}
	documents_validation_errors = []

	for doc in documents:
		if isinstance(doc, tuple) and len(doc) == 2:
			document, summary = doc
		else:
			document = doc
			summary = getattr(document, 'grouped_plans', {})

		# Суммируем планы по покупателям
		for customer, months_data in summary.items():
			if customer not in combined_plans:
				combined_plans[customer] = [0.0] * 12

			for i, value in enumerate(months_data):
				if value is not None:
					combined_plans[customer][i] += value

	table = Table(
		show_header=True,
		header_style="bold magenta",
		show_lines=True,
		title=(
			f"\nИтоговые планы закупок с "
			f"[cyan bold]{start_num}[/cyan bold] по [cyan bold]{start_num + len(documents) - 1}[/cyan bold]"
		)
	)

	table.add_column("№", style="white", width=3)
	table.add_column("Контрагенты", style="green", width=25)

	# Месяцы
	months = get_localized_months_list()
	for month in months:
		table.add_column(month, width=6, justify="right")

	table.add_column("Откл (-)", width=8, justify="center", style="bold yellow")

	# Заполняем таблицу данными из каждого документа
	for idx, doc in enumerate(documents, start_num):
		if isinstance(doc, tuple) and len(doc) == 2:
			document, summary = doc
		else:
			document = doc
			summary = getattr(document, 'grouped_plans', {})

		# Для каждого покупателя в документе создаем отдельную строку с помесячными планами закупок
		for customer_idx, (customer, months_data) in enumerate(summary.items()):
			customer_display = format_string_list(document.customer_names) if customer == "all" else customer

			# Данные по месяцам
			row_data = [str(idx), customer_display]
			total_customer = 0.0

			for value in months_data:
				if value is not None and value > 0:
					display_value = f"{int(value)}" if value == int(value) else f"{value:.1f}"
					row_data.append(display_value)
					total_customer += value
				else:
					row_data.append("—")

			table.add_row(*row_data, document.allowed_deviation)

		if document.has_validation_errors:
			documents_validation_errors.extend(document.validation_errors_list)

	console.print(table)
	if documents_validation_errors:
		console.print(
			f"❌ Обнаружены ошибки в документах:\n"
			f"[red]{format_string_list(documents_validation_errors)}[/red]"
		)


def preview_document_plans(summary: dict) -> None:
	"""Показывает одним списком планы закупом по всем покупателям"""
	if not summary:
		return

	# Для каждого покупателя создаем свою таблицу
	for idx, (customer_name, monthly_data) in enumerate(summary.items(), 1):
		if customer_name != "all":
			console.print(f"\n👤 Покупатель {idx}: [bold cyan]{customer_name}[/bold cyan]")

		# Создаем таблицу для этого покупателя
		table = Table(show_header=True, header_style="bold blue", show_lines=True)

		months = get_localized_months_list() + ["Итого"]

		for month in months:
			table.add_column(month, width=7, justify="right")

		# Данные по месяцам
		monthly_values = [f"{val:.2f}" if val is not None else "—" for val in monthly_data]

		# Считаем итог
		total = sum(val for val in monthly_data if val is not None)
		monthly_values.append(f"[bold]{total:.2f}[/bold]")

		table.add_row(*monthly_values)
		console.print(table)


def preview_document_info(document: 'DocumentCreate', title: str = "Предпросмотр документа"):
	"""Создает таблицу для предпросмотра документов с пагинацией"""

	if not document:
		console.print("📭 Нет документов для просмотра", style="yellow")
		return

	table = Table(
		title=f"{title}" or None,
		show_header=True,
		header_style="bold magenta"
	)

	# Колонки
	table.add_column("Файл", style="blue", width=30)
	table.add_column("Контрагенты", style="green", width=30)
	table.add_column("№ соглашения", style="white", width=12)
	table.add_column("Год", style="white", width=5)
	table.add_column("Откл (-)", style="yellow", width=8)
	table.add_column("Ошибки", style="red", width=40)

	file_path = Path(document.file_path).name
	customer_names = format_string_list(document.customer_names, default_text="не определен")
	errors = format_string_list(document.validation_errors)

	table.add_row(
		file_path,
		customer_names,
		document.agreement_number or "—",
		str(document.year or "—"),
		document.allowed_deviation or "—",
		errors or "—"
	)

	# Показываем текущую порцию
	console.print(table)
