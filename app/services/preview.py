from pathlib import Path
from typing import TYPE_CHECKING

from rich.table import Table

from app.config import settings
from app.utils.base import format_string_list
from app.utils.console import confirm_prompt, console

if TYPE_CHECKING:
	from app.models import Document, DocumentCreate


def preview_export_data(documents: list['Document'], year: int) -> None:
	"""Полный предпросмотр данных для экспорта с постраничным выводом"""

	console.print(f"\n📊 Предпросмотр данных для экспорта за {year} год", style="bold green")
	console.print("=" * 60, style="dim")

	# Сводная статистика
	with_errors = sum(1 for doc in documents if doc.validation_errors)

	console.print(f"📁 Документов: {len(documents)}")
	console.print(f"⚠️ С ошибками: {with_errors}")
	console.print("=" * 60, style="dim")

	# Постраничный вывод документов
	batch_size = settings.CONSOLE_OUTPUT_BATCH_SIZE
	current_batch = 0

	for i, document in enumerate(documents, 1):
		# Выводим информацию о документе
		console.print(f"\n📄 Файл {i}/{len(documents)}: [bold cyan]{Path(document.file_path).name}[/bold cyan]")
		console.print("." * 60, style="dim")

		# Основная информация о документе
		console.print(f"📝 Соглашение: [cyan bold]{document.agreement_number or '—'}[/cyan bold]")
		console.print(f"📅 Год: [cyan bold]{document.year or '—'}[/cyan bold]")
		console.print(f"👥 Контрагенты: [green bold]{', '.join(document.customer_names_list)}[/green bold]")
		console.print(f"📏 Допустимое отклонение: {document.allowed_deviation or '—'}")

		# Ошибки валидации
		if document.validation_errors:
			console.print("❌ Ошибки валидации:", style="red")
			for error in document.validation_errors:
				console.print(f"   ⚠️  [yellow]{error}[/yellow]")

		# Планы закупок по месяцам
		if document.plans:
			console.print("\n📈 План закупок по месяцам:", style="bold")
			preview_monthly_data(document)
		else:
			console.print("📈 Планы закупок: [red]отсутствуют[/red]")

		# Пауза после каждого batch_size документов
		if i % batch_size == 0 and i < len(documents):
			console.print(f"📖 Показано {i} из {len(documents)} документов.\n")

			if not confirm_prompt("Продолжить просмотр?", default=True):
				console.print("👀 Просмотр прерван пользователем", style="yellow")
				break

			console.print("." * 60, style="dim")

		current_batch = i

	# Итоговая статистика
	console.print(f"\n🎯 Просмотр завершен.", style="bold green")

	if current_batch < len(documents):
		console.print(f"👀 Пропущено документов: {len(documents) - current_batch}", style="yellow")


def preview_document_data(
		documents: list['Document'] | list['DocumentCreate'] | None,
		title: str = "Предпросмотр данных"
) -> Table:
	"""Создает таблицу для предпросмотра документов"""

	table = Table(title=title, show_header=True, header_style="bold magenta")

	# Колонки как в экспорте
	table.add_column("Файл", style="cyan", width=30)
	table.add_column("Контрагенты", style="green", width=40)
	table.add_column("№ соглашения", style="yellow", width=12)
	table.add_column("Год", style="blue", width=5)
	table.add_column("Отклонение +/-", style="gold1", width=15)
	table.add_column("Ошибки", style="red", width=25)

	for doc in documents:
		# Форматируем данные как в экспорте
		customer_names = format_string_list(doc.customer_names, default_text="не определен", max_line_length=25)
		errors = format_string_list(doc.validation_errors, max_line_length=25)

		table.add_row(
			Path(doc.file_path).name,
			customer_names,
			doc.agreement_number or "—",
			str(doc.year or "—"),
			doc.allowed_deviation,
			errors
		)

	return table


def preview_monthly_data(document: 'Document') -> None:
	"""Показывает месячные данные с группировкой по покупателям"""
	if not document.plans:
		return

	summary = document.get_plans_summary()

	# Для каждого покупателя создаем свою таблицу
	for idx, (customer_name, monthly_data) in enumerate(summary.items(), 1):
		if customer_name != "all":
			console.print(f"\n👤 Покупатель {idx}: [bold cyan]{customer_name}[/bold cyan]")

		# Создаем таблицу для этого покупателя
		table = Table(show_header=True, header_style="bold green", show_lines=True)

		months = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек", "Итого"]

		for month in months:
			table.add_column(month, width=8, justify="right")

		# Данные по месяцам
		monthly_values = [f"{val:.1f}" if val is not None else "—" for val in monthly_data]

		# Считаем итог
		total = sum(val for val in monthly_data if val is not None)
		monthly_values.append(f"[bold]{total:.1f}[/bold]")

		table.add_row(*monthly_values)
		console.print(table)
