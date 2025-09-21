#!/usr/bin/env python3
"""
Расширенный тестовый скрипт с пошаговой проверкой парсера
"""
from pathlib import Path
import json
from app.db import init_db, get_db
from app.services.document_parser import DocumentParser
from app.services.utils import parse_file_to_text, find_documents, get_current_year
from app import crud
from app.config import settings


def step1_find_files():
	"""Шаг 1: Проверка загрузки файлов из папки"""
	print("=" * 60)
	print("🔍 ШАГ 1: Поиск файлов в папке данных")
	print("=" * 60)

	# Выбор лимита файлов
	limit_input = input("Лимит файлов для показа (оставьте пустым для всех): ").strip()

	try:
		file_limit = int(limit_input) if limit_input else None
	except ValueError:
		print("❌ Неверный формат числа")
		return []

	data_dir = settings.DATA_DIR
	print(f"Папка данных: {data_dir}")
	print(f"Поддерживаемые форматы: {settings.SUPPORTED_FORMATS}")

	if not data_dir.exists():
		print("❌ Папка данных не существует!")
		return []

	files = list(find_documents(data_dir))

	# Применяем лимит
	if file_limit is not None:
		files = files[:file_limit]
		print(f"📁 Найдено файлов (ограничение до: {file_limit}): {len(files)}")
	else:
		print(f"📁 Найдено файлов: {len(files)}")

	for i, file_path in enumerate(files, 1):
		print(f"   {i}. {file_path.name} ({file_path.suffix})")

	return files


def step2_convert_to_text(files):
	"""Проверка преобразования в текст"""
	print("\n" + "=" * 60)
	print("📝 ШАГ 2: Преобразование файлов в текст")
	print("=" * 60)

	if not files:
		print("❌ Нет файлов для обработки")
		return

	for i, file_path in enumerate(files, 1):
		print(f"\n📄 Файл {i}: {file_path.name}")
		print("-" * 40)

		try:
			text = parse_file_to_text(file_path)
			if text:
				# Показываем первые 500 символов для preview
				preview = text[:500].replace('\n', ' ')
				print(f"   Preview:\n{preview}... (укорочено до 500 символов)\n")

				# Показываем табличные данные если они есть
				lines = text.split('\n')
				table_lines = [
					line for line in lines if any(char.isdigit() for char in line) and len(line.strip()) > 10
				]

				if table_lines:
					print(f"   📊 Найдено {len(table_lines)} строк с табличными данными:")
					for table_line in table_lines[:5]:  # Первые 5 строк таблицы
						print(f"      {table_line.strip()}")
			else:
				print("   ❌ Не удалось извлечь текст")

		except Exception as e:
			print(f"   ❌ Ошибка: {e}")


def step4_parse_documents(files, with_save=False):
	"""Парсинг документов"""
	print("\n" + "=" * 60)
	print(f"⚙️  ШАГ {4 if with_save else 3}: Парсинг документов")
	print("=" * 60)

	init_db()  # Инициализируем БД

	if not files:
		print("❌ Нет файлов для обработки")
		return

	parser = DocumentParser()

	with next(get_db()) as db:
		for i, file_path in enumerate(files, 1):
			print(f"\n📄 Файл {i}: {file_path.name}")
			print("-" * 40)

			if with_save:
				crud.delete_all_documents(db)

			try:
				# Парсим документ
				document_data = parser.parse_document(file_path)

				if document_data:
					print(f"✅ Документ успешно распарсен {'с сохранением в БД' if with_save else 'без сохранения'}!")
					print(f"   Номер: {document_data.agreement_number}")
					print(f"   Год: {document_data.year}")
					print(f"   Покупатели: {document_data.customer_names}")
					print(f"   Планов: {len(document_data.product_plans)}")

					# Показываем первые 5 планов
					for plan in document_data.product_plans[:5]:
						print(f"      {plan.month:02d}.{plan.year}: {plan.planned_quantity}т - {plan.product_name}")

					if document_data.validation_errors:
						print(f"   ⚠️  Ошибки: {document_data.validation_errors}")

					# Проверяем, не обработан ли уже файл
					existing = crud.get_document_by_file_path(db, str(file_path))
					if existing:
						print(f"   ⏭️  Уже обработан ранее (ID: {existing.id})")
						continue

					if with_save:
						# Сохраняем в БД
						document = crud.create_document(db, document_data)
						print(f"   💾 Сохранено в БД с ID: {document.id}")
				else:
					print("   ❌ Не удалось распарсить документ")

			except Exception as e:
				print(f"   ❌ Ошибка парсинга: {e}")
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

	with next(get_db()) as db:
		# Документы за выбранный год
		documents = crud.get_documents_with_plans(db, year=year, limit=limit)

		print(f"📊 Документов за {year} год: {len(documents)}")

		for i, doc in enumerate(documents, 1):
			print(f"\n📄 Документ {i}: {doc.agreement_number or 'Без номера'}")
			print(f"   ID: {doc.id}")
			print(f"   Файл: {Path(doc.file_path).name}")
			print(f"   Год: {doc.year}")

			if doc.customer_names:
				customers = json.loads(doc.customer_names)
				print(f"   Покупатели: {', '.join(customers)}")

			if doc.product_plans:
				print(f"   📈 Планов поставок: {len(doc.product_plans)}")

				# Группируем планы по продуктам
				products = {}
				for plan in doc.product_plans:
					if plan.product_name not in products:
						products[plan.product_name] = []
					products[plan.product_name].append(plan)

				for product_name, plans in products.items():
					total = sum(p.planned_quantity for p in plans if p.planned_quantity)
					# Добавляем информацию об отклонениях
					deviations = [p.allowed_deviation for p in plans if p.allowed_deviation]
					deviation_info = f", отклонения: {', '.join(set(deviations))}" if deviations else ""
					print(f"      {product_name}: {total}т ({len(plans)} месяцев{deviation_info})")

			if doc.validation_errors:
				errors = json.loads(doc.validation_errors)
				print(f"   ⚠️  Ошибки (всего {len(errors)}):")
				for error in errors:
					print(f"      - {error}")


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
			print(f"\n📄 Документ {i}: {doc.agreement_number or 'Без номера'}")
			print(f"   ID: {doc.id}")
			print(f"   Файл: {Path(doc.file_path).name}")
			print(f"   Год: {doc.year}")

			if doc.validation_errors:
				errors = json.loads(doc.validation_errors)
				print(f"   ❌ Ошибки ({len(errors)}):")
				for error in errors:
					print(f"      - {error}")

			if doc.product_plans:
				print(f"   📈 Планов: {len(doc.product_plans)}")


def step8_clear_database():
	"""Очистка базы данных"""
	print("\n" + "=" * 60)
	print("🧹 ШАГ 8: Очистка базы данных (с выбором года)")
	print("=" * 60)

	print("1. ❌ Удалить ВСЕ документы")
	print("2. 📅 Удалить документы за определенный год")
	print("3. ↩️  Назад")

	choice = input("\nВаш выбор (1-3): ").strip()

	with next(get_db()) as db:
		if choice == "1":
			deleted = crud.delete_all_documents(db)
			print(f"🧹 Удалено ВСЕХ документов: {deleted}")

		elif choice == "2":
			year_input = input("Введите год для очистки: ").strip()
			try:
				year = int(year_input)
				deleted = crud.delete_documents_by_year(db, year=year)
				print(f"🧹 Удалено документов за {year} год: {deleted}")
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
		print("8. 🧹 Очистить базу данных")
		print("9. 👋 Выход")

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
		elif choice == "8":
			step8_clear_database()
		elif choice == "9":
			print("👋 До свидания!")
			break
		else:
			print("❌ Неверный выбор, попробуйте снова")

		input("\n⏎ Нажмите Enter чтобы продолжить...")


if __name__ == "__main__":
	main()
