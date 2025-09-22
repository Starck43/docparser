from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.config import settings

console = Console()


def print_success(message: str) -> None:
	"""Печатает успешное сообщение"""
	console.print(f"✅  [green]{message}[/green]")


def print_error(message: str) -> None:
	"""Печатает сообщение об ошибке"""
	console.print(f"❌ [red]{message}[/red]")


def print_warning(message: str) -> None:
	"""Печатает предупреждение"""
	console.print(f"⚠️  [yellow]{message}[/yellow]")


def print_table(title: str, **columns: str) -> Table:
	"""Создает таблицу с форматированием для вывода контекста."""

	table = Table(title=title)
	for col_name, col_style in columns.items():
		table.add_column(col_name, style=col_style)
	return table


def confirm_prompt(message: str, default: bool = True) -> bool:
	"""Кастомное подтверждение с русскими д/н"""

	choices = "Д/н" if default else "д/Н"
	prompt = f"{message} [{choices}]: "

	while True:
		try:
			choice = console.input(prompt).lower().strip()
			if not choice:  # Если нажат Enter
				return default  # <-- This should return the default value
			if choice in ['д', 'да', 'y', 'yes']:
				return True
			elif choice in ['н', 'нет', 'n', 'no']:
				return False
			else:
				console.print("❌ Пожалуйста, введите 'д' или 'н'", style="red")
		except (KeyboardInterrupt, EOFError):
			console.print("\n❌ Отменено пользователем", style="red")
			raise typer.Abort()


def input_path(prompt: str, default: Path = settings.DATA_DIR) -> Path:
	"""Запрос пути с подсказкой"""
	console.print(f"{prompt} [cyan]{default.absolute()}[/cyan]", style="bold")
	custom_input = console.input("🔍 Введите свой путь (или Enter для пропуска): ").strip()
	return Path(custom_input or default)


def select_directory(default_dir: Path, create_if_not_exists: bool = False) -> Path | None:
	"""Выбор директории с валидацией"""

	custom_path = input_path("Текущий путь:", default_dir)
	if not custom_path.exists():
		print_error("Папка не существует!")
		if create_if_not_exists and confirm_prompt("Создать папку?", default=True):
			custom_path.mkdir(parents=True, exist_ok=True)
			return custom_path

		return

	return custom_path
