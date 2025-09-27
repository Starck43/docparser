from app.config import settings
from app.core.pipeline import parse_files_pipeline
from app.services.export import export_documents_to_file
from app.services.files import display_files_tree
from app.services.preview import paginated_preview, preview_documents_details
from app.utils.base import get_current_year
from app.utils.console import confirm_prompt, console, print_warning, select_directory, print_error
from app.utils.files import find_files

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

	files = find_files(data_dir)
	if not files:
		print_error("Файлы не найдены")
		return 0

	files = display_files_tree(files)

	if not confirm_prompt("Начать парсинг файлов?", default=True):
		return 0

	return parse_files_pipeline(files, year=get_current_year())


def run_preview():
	"""Просмотр помесячных планов закупок за текущий год"""

	year = get_current_year()
	paginated_preview(
		title=f" Детальный просмотр сохраненных документов за {year}",
		func=preview_documents_details,
		year=year
	)


def run_export():
	"""Выполняет экспорт данных за текущий год"""

	console.print("💾 Выбор папки для экспорта", style="bold")
	output_dir = select_directory(settings.EXPORT_DIR, create_if_not_exists=True)
	if not output_dir:
		return

	year = get_current_year()
	export_documents_to_file(
		year=year,
		output_dir=output_dir,
		title=f"Экспорт помесячных планов закупок за {year} год"
	)


def main():
	console.print("\n" + "=" * 45, style="dim")
	console.print("📄 Сбор информации из файлов и экспорт данных", style="bold blue")
	console.print("=" * 45, style="dim")

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
