from app.export import export_to_xls_with_months
from app.services.file_service import find_files, display_files_tree
from app.services.parser_service import parse_files
from app.utils.base import get_current_year


def main():
	print("📄 СБор информации из файлов и экспорт в XLS")

	# Находим файлы
	files = find_files()
	display_files_tree(files)

	if input("Продолжить парсинг? (д/н): ").lower() in ['д', 'да', 'y', 'yes']:
		documents = parse_files(files)
		print(f"✅ Обработано документов: {len(documents)}")

		# if input("Экспортировать результаты? (д/н): ").lower() in ['д', 'да', 'y', 'yes']:
		# 	year = get_current_year()
		# 	export_path = export_to_xls_with_months(documents, year)
		# 	print(f"✅ Экспорт завершен: {export_path}")


if __name__ == "__main__":
	main()
