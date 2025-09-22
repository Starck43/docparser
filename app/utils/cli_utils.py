import typer
from rich.console import Console
from rich.table import Table

console = Console()


def print_success(message: str) -> None:
	"""Печатает успешное сообщение"""
	console.print(f"\n✅ [green]{message}[/green]")


def print_error(message: str) -> None:
	"""Печатает сообщение об ошибке"""
	console.print(f"\n❌ [red]{message}[/red]")


def print_warning(message: str) -> None:
	"""Печатает предупреждение"""
	console.print(f"\n⚠️  [yellow]{message}[/yellow]")


def confirm_prompt(message: str, default: bool = True) -> bool:
	"""Кастомное подтверждение с русскими д/н"""

	choices = "Д/н" if default else "д/Н"
	prompt = f"{message} [{choices}]: "

	while True:
		try:
			choice = console.input(prompt).lower().strip()
			if choice in ['д', 'да', 'y', 'yes', '']:
				return True
			elif choice in ['н', 'нет', 'n', 'no']:
				return False
			else:
				console.print("❌ Пожалуйста, введите 'д' или 'н'", style="red")
		except (KeyboardInterrupt, EOFError):
			console.print("\n❌ Отменено пользователем", style="red")
			raise typer.Abort()


def create_table(title: str, **columns: str) -> Table:
	"""Создает таблицу с форматированием для вывода контекста."""

	table = Table(title=title)
	for col_name, col_style in columns.items():
		table.add_column(col_name, style=col_style)
	return table
