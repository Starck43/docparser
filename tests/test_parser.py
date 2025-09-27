#!/usr/bin/env python3
"""
Расширенный тестовый скрипт с пошаговой проверкой парсера
"""
import json
from pathlib import Path

from app import crud
from app.config import settings
from app.crud import get_documents_with_grouped_plans
from app.db import init_db, get_db
from app.services.export import export_plans_to_xls
from app.services.files import display_files_tree, convert_file_to_text
from app.services.parser import DocumentParser
from app.services.preview import preview_document_info, preview_document_plans, paginated_preview, preview_documents_details
from app.services.tables import print_formatted_table
from app.utils.base import get_current_year, format_string_list
from app.utils.console import console, print_error


def step1_find_files():
	"""Шаг 1: Проверка загрузки файлов из папки"""
	print("=" * 60)
	print("🔍 ШАГ 1: Поиск файлов в папке данных")
	print("=" * 60)

	return display_files_tree(settings.DATA_DIR)


def step2_convert_to_text(files):
	"""Шаг 2: Проверка преобразования документа в текст и таблицы"""
	print("\n" + "=" * 60)
	print("📝 ШАГ 2: Преобразование файлов в текст и таблицы")
	print("=" * 60)

	if not files:
		return

	# Выбор года
	year_input = input("Введите год (оставьте пустым для текущего года): ").strip()

	try:
		year = int(year_input) if year_input else get_current_year()
	except ValueError:
		print("❌ Неверный формат года")
		return

	for i, file_path in enumerate(files, 1):
		print(f"\n📄 Файл {i}: {file_path.name}")
		print("-" * 60)

		try:
			# 1. Извлекаем текст с таблицами
			text, tables = convert_file_to_text(file_path, year)

			if text:
				preview = text[:450] + "..." if len(text) > 400 else text
				print(f"{preview}")

			if tables:
				print(f"   📊 Найдено таблиц: {len(tables)}\n")
				# Дополнительная информация о таблицах
				for table_idx, table_data in enumerate(tables, 1):
					print(f"   📋 ТАБЛИЦА {table_idx}")
					print(f"   📏 Размер: {len(table_data)}×{len(table_data[0]) if table_data else 0}")
					print(f"   📋 Источник: {file_path.name}")
					print_formatted_table(table_data, f"ТАБЛИЦА {table_idx}", max_col_width=15)
			else:
				print("   📊 Таблицы: не обнаружено")

		except Exception as e:
			print(f"❌ Ошибка: {e}")


def step4_parse_documents(files, with_save=False):
	"""Парсинг документов"""
	print("\n" + "=" * 60)
	print(f"⚙️  ШАГ {4 if with_save else 3}: Парсинг документов")
	print("=" * 60)

	if not files:
		return

	# Выбор года
	year_input = input("Введите год (оставьте пустым для текущего года): ").strip()

	try:
		year = int(year_input) if year_input else get_current_year()
	except ValueError:
		print("❌ Неверный формат года")
		return

	parser = DocumentParser()

	with next(get_db()) as db:
		for i, file_path in enumerate(files, 1):
			print(f"\n📄 [{i}]: {file_path.name}")

			try:
				# Парсим документ
				data = convert_file_to_text(file_path)
				if not data:
					return None

				document_data = parser.parse_document(str(file_path.name), data, year)

				if document_data:
					if document_data.validation_errors:
						print_error(f"Документ некорректно распарсен. Ошибки: {document_data.validation_errors}")
					else:
						if with_save:
							# Сохраняем в БД
							document, status = crud.save_document(db, document_data)
							if status == "created":
								status = f"(💾 Создано)"
							else:
								status = f"(Обновлено)"
						else:
							status = ""

						table_title = f"👥 Контрагенты: {format_string_list(document_data.customer_names).upper()} {status}"
						console.print(table_title, style="dim")
						preview_document_info(document_data, title="")
						summary = document_data.get_plans_summary()
						preview_document_plans(summary)

				else:
					print("❌ Не удалось распарсить документ")

			except Exception as e:
				print(f"❌ Ошибка парсинга: {e}")
				import traceback
				traceback.print_exc()


def step5_view_documents():
	"""Просмотр сохраненных документов"""
	print("\n" + "=" * 60)
	print("📋 ШАГ 5: Просмотр документов в базе данных за указанный год")
	print("=" * 60)

	# Выбор года
	year_input = input("Введите год (оставьте пустым для текущего): ").strip()

	try:
		year = int(year_input) if year_input else get_current_year()
	except ValueError:
		print("❌ Неверный формат года")
		return

	# Выбор количества
	limit_input = input("Сколько документов показать? (оставьте пустым для всех): ").strip()

	try:
		limit = int(limit_input) if limit_input else None
	except ValueError:
		print("❌ Неверный формат числа")
		return

	paginated_preview(
		title=f" Детальный просмотр сохраненных документов за {year}",
		func=preview_documents_details,
		year=year,
		limit=limit
	)


def step6_all_steps():
	"""Полный цикл тестирования"""
	print("🚀 Запуск полного цикла тестирования")

	files = step1_find_files()
	if files:
		input("\n⏎ Нажмите Enter для продолжения к шагу 2...")
		step2_convert_to_text(files)

		input("\n⏎ Нажмите Enter для продолжения к шагу 4...")
		step4_parse_documents(files, with_save=True)

		input("\n⏎ Нажмите Enter для продолжения к шагу 5...")
		step5_view_documents()


def step7_documents_with_errors():
	"""Документы с ошибками валидации"""
	print("\n" + "=" * 60)
	print("⁉️ ШАГ 7: Документы с ошибками в БД")
	print("=" * 60)

	# Выбор года
	year_input = input("Введите год (оставьте пустым для всех лет): ").strip()

	try:
		year = int(year_input) if year_input else None
	except ValueError:
		print("❌ Неверный формат года")
		return

	# Выбор количества
	limit_input = input("Сколько документов показать? (оставьте пустым для всех): ").strip()

	try:
		limit = int(limit_input) if limit_input else None
	except ValueError:
		print("❌ Неверный формат числа")
		return

	with next(get_db()) as db:
		error_docs = crud.get_documents_with_errors(db, year=year, limit=limit)

		year_desc = f"за {year} год" if year else "за все годы"
		print(f"📊 Документов с ошибками {year_desc}: {len(error_docs)}")

		for i, doc in enumerate(error_docs, 1):
			print(f"\n📄 [{i:03d}]: Дополнительное соглашение {doc.agreement_number or '<без номера>'}")
			print(f"   ID: {doc.id}")
			print(f"   Файл: {Path(doc.file_path).name}")
			print(f"   Год: {doc.year}")

			if doc.validation_errors:
				errors = json.loads(doc.validation_errors)
				print(f"   ❌ Ошибки ({len(errors)}):")
				for error in errors:
					print(f"      - {error}")


def step8_export_to_xls():
	"""Тестирует создание XLS файла с данными."""

	print("\n" + "=" * 60)
	print("📋 ШАГ 8: Экспорт данных за указанный год")
	print("=" * 60)

	# Выбор года
	year_input = input("Введите год (оставьте пустым для текущего): ").strip()

	try:
		year = int(year_input) if year_input else get_current_year()
	except ValueError:
		print("❌ Неверный формат года")
		return

	with next(get_db()) as db:
		# Получаем документы с планами (используем обычный get_documents)
		documents = crud.get_documents(db, year=year)

		# Вызываем функцию экспорта
		export_file_path = export_plans_to_xls(list(documents), year)

		# Проверяем, что файл создался
		assert export_file_path.exists(), "XLS файл не был создан"


def step9_clear_database():
	"""Очистка базы данных"""
	print("\n" + "=" * 60)
	print("🧹 ШАГ 9: Очистка базы данных (с выбором года)")
	print("=" * 60)

	print("1. ❌ Удалить ВСЕ документы")
	print("2. 📅 Удалить документы за определенный год")
	print("3. ↩️  Назад")

	choice = input("\nВаш выбор (1-3): ").strip()

	with next(get_db()) as db:
		if choice == "1":
			from app.crud import delete_all_documents
			deleted_count = delete_all_documents(db)
			print(f"✅ Удалено ВСЕХ документов: {deleted_count}")

		elif choice == "2":
			year_input = input("Введите год для удаления: ").strip()
			try:
				year = int(year_input)
				deleted = crud.delete_documents_by_year(db, year=year)
				print(f"✅ Удалено документов за {year} год: {deleted}")
			except ValueError:
				print("❌ Неверный формат года")

		elif choice == "3":
			return
		else:
			print("❌ Неверный выбор")


def main():
	"""Главное меню"""
	print("🧪 ТЕСТОВЫЙ ПАРСЕР ДОКУМЕНТОВ")
	print("=" * 40)

	while True:
		print("\nВыберите вариант тестирования:")
		print("1. 🔍 Только поиск файлов")
		print("2. 📝 Только преобразование в текст")
		print("3. ⚙️ Парсинг документа (без сохранения)")
		print("4. ⚙️ Парсинг документа (с сохранением в БД)")
		print("5. 📋 Только просмотр документов")
		print("6. 🚀 Полный цикл тестирования")
		print("7. ⁉️ Показать сохраненные документы с ошибками")
		print("8. 🧾 Экспортировать данные в файл")
		print("9. 🧹 Очистить базу данных")
		print("\n0. 👋 Выход")

		choice = input("\nВаш выбор (1-9): ").strip()

		if choice == "1":
			step1_find_files()
		elif choice == "2":
			files = step1_find_files()
			step2_convert_to_text(files)
		elif choice == "3":
			files = step1_find_files()
			step4_parse_documents(files)
		elif choice == "4":
			init_db()
			files = step1_find_files()
			step4_parse_documents(files, with_save=True)
		elif choice == "5":
			step5_view_documents()
		elif choice == "6":
			step6_all_steps()
		elif choice == "7":
			step7_documents_with_errors()
		elif choice == '8':
			step8_export_to_xls()
		elif choice == "9":
			step9_clear_database()
		else:
			print("👋 До свидания!")
			break

		input("\n⏎ Нажмите Enter чтобы продолжить...")


if __name__ == "__main__":
	main()
