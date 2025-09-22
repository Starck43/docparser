from app.services.file_service import find_files, display_files_tree, parse_files
from app.utils.cli_utils import confirm_prompt, console, print_success


def main():
	console.print("📄 СБор информации из файлов и экспорт в XLS")

	# Находим файлы
	files = find_files()
	display_files_tree(files)

	if confirm_prompt("Продолжить парсинг?", default=True):
		documents = parse_files(files)
		print_success(f"✅ Обработано документов: {len(documents)}")

		# if input("Экспортировать результаты? (д/н): ").lower() in ['д', 'да', 'y', 'yes']:
		# 	year = get_current_year()
		# 	export_path = export_to_xls_with_months(documents, year)
		# 	print(f"✅ Экспорт завершен: {export_path}")


if __name__ == "__main__":
	main()
