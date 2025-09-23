from app.config import settings
from app.crud import get_documents
from app.db import get_db
from app.services.export import export_to_xls_with_months
from app.services.files import display_files_tree
from app.services.parser import main_file_parser
from app.utils.base import get_current_year
from app.utils.console import (confirm_prompt, console, print_success, print_warning, select_directory, print_error)

try:
	import questionary

	HAS_QUESTIONARY = True
except ImportError:
	import questionary

	HAS_QUESTIONARY = False
	print_warning(
		"Для возможности работать с интерактивным меню установите библиотеку в окружение: pip install questionary"
	)


def run_parsing() -> int:
	"""Выполняет парсинг файлов и возвращает количество обработанных документов"""
	console.print("💾 Выбор папки с файлами:", style="bold")
	data_dir = select_directory(settings.DATA_DIR, create_if_not_exists=False)
	if not data_dir:
		return 0

	files = display_files_tree(data_dir)
	if not files:
		return 0

	if not confirm_prompt("Начать парсинг файлов?", default=True):
		return 0

	return main_file_parser(files, year=get_current_year())


def run_preview():
	with next(get_db()) as db:
		target_year = get_current_year()
		documents = get_documents(db, year=target_year)

		if not documents:
			print_error(f"Нет документов за {target_year} год")
			return

		from app.services.preview import preview_export_data
		console.print(f"Просмотр сохраненных данных за {target_year} год", style="green")
		preview_export_data(list(documents), target_year)
		return


def run_export():
	"""Выполняет экспорт данных за текущий год"""
	console.print("💾 Выбор папки для экспорта:", style="bold")
	export_dir = select_directory(settings.EXPORT_DIR, create_if_not_exists=True)
	if not export_dir:
		return

	year = get_current_year()
	with next(get_db()) as db:
		documents = get_documents(db, year=year)
		if not documents:
			print_warning(f"Нет документов за {year} год")
			return

		export_path = export_to_xls_with_months(list(documents), year, export_dir)
		abs_path = export_path.absolute()

		print_success(f"Экспорт успешно завершен. Сохранено документов: [cyan]{len(documents)}[/cyan]")

		console.print("\n" + "=" * 80, style="dim")
		console.print("📂 Ссылка для открытия файла:", style="bold")
		console.print(f"📍 [link=file://{abs_path}]{abs_path}[/link]", style="blue underline")
		console.print("=" * 80, style="dim")


def main():
	console.print("\n" + "=" * 80, style="dim")
	console.print("📄 Сбор информации из файлов и экспорт данных", style="bold green")
	console.print("=" * 80, style="dim")

	while True:
		# Интерактивное меню с questionary (если установлен)
		if HAS_QUESTIONARY:
			choice = questionary.select(
				"🎯 Выберите действие:",
				choices=[
					questionary.Choice("📁 Парсинг файлов", value="parse"),
					questionary.Choice("📊 Просмотр результата", value="preview"),
					questionary.Choice("🖥 Экспорт данных", value="export"),
					questionary.Choice("🚪 Выйти", value="exit")
				],
				pointer="👉"
			).ask()
		else:
			# Простое меню если questionary не установлен
			console.print("\n🎯 Выберите действие:", style="bold")
			console.print("1. 📁 Начать парсинг файлов")
			console.print("2. 🖥 Просмотр результата")
			console.print("3. 📊 Выполнить экспорт данных")
			console.print("4. 🚪 Выйти")

			choice_map = {"1": "parse", "2": "preview", "3": "export", "4": "exit"}
			choice_input = console.input("\nВаш выбор (1-4): ").strip()
			choice = choice_map.get(choice_input, "")

		if choice == "parse":
			documents_count = run_parsing()

			if documents_count > 0 and confirm_prompt("\nЖелаете посмотреть полученный результат?", default=True):
				run_preview()

		elif choice == "preview":
			run_preview()

		elif choice == "export":
			run_export()

		elif choice == "exit":
			console.print("👋 До свидания!", style="green")
			break

		else:
			print_warning("Неверный выбор, попробуйте снова")
			continue

		# Предложение повторить
		if not confirm_prompt("\nВыполнить еще одну операцию?", default=False):
			console.print("👋 До свидания!", style="green")
			break


if __name__ == "__main__":
	main()
