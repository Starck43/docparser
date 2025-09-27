import re
from pathlib import Path
from typing import Optional, Any

from app.config import settings
from app.crud import create_document, update_document, get_document_by_slug, bulk_save_documents
from app.db import get_db
from app.models import DocumentCreate, ProductPlanCreate
from app.services.files import convert_file_to_text
from app.utils.base import get_current_year, format_string_list, slugify_filename
from app.utils.console import console, print_error


def main_file_parser(
		files: list[Path],
		year: int,
		save_to_db: bool = True,  # dry-run режим
		update_mode: bool = False,  # False = пропускать, True = перезаписывать
		use_bulk: bool = True
) -> int:
	"""
	Парсит переданные файлы, сохраняет и возвращает список документов.
	Возвращает количество обработанных документов.
	"""

	parser = DocumentParser()
	bulk_buffer: list['DocumentCreate'] = []
	processed = skipped = updated = 0

	for i, file_path in enumerate(files, 1):
		try:
			# Извлекаем данные из файла (data[0] - текст, data[1] - таблицы)
			data = convert_file_to_text(file_path)
			if not data[0]:
				skipped += 1
				continue

			# Парсим документы за указанный год
			document_data = parser.parse_document(str(file_path.name), data=data, year=year)

			# Фильтр по году
			if not document_data.plans:
				full_status = parser.format_status(document_data.validation_errors, True, False)
				console.print(f"[{i:03d}/{len(files)}]: [grey]{file_path.name}[/grey] ... {full_status}")
				skipped += 1
				continue

			with next(get_db()) as db:
				existing_doc = get_document_by_slug(db, document_data.slug)

				if existing_doc:
					if update_mode:
						if save_to_db and not use_bulk:
							document_data = update_document(db, existing_doc.id, document_data)
						updated += 1
					else:
						full_status = parser.format_status(document_data.validation_errors, True, update_mode)
						console.print(f"[{i:03d}/{len(files)}]: [grey]{file_path.name}[/grey] ... {full_status}")
						skipped += 1
						continue
				else:
					if save_to_db and not use_bulk:
						document_data = create_document(db, document_data)

				# Если bulk-режим — откладываем для массовой вставки
				if save_to_db and use_bulk:
					bulk_buffer.append(document_data)

			processed += 1

			# Формируем статус для отображения на экране
			full_status = parser.format_status(document_data.validation_errors, bool(existing_doc), update_mode)

			# Вывод в консоль
			console.print(f"[{i:03d}/{len(files)}]: [gray]{file_path.name}[/gray] ... {full_status}")

			if document_data.validation_errors:
				console.print(f"          ⚠️  [red]{format_string_list(document_data.validation_errors, separator=', ')}[/red]")

		except Exception as e:
			print_error(f"Ошибка обработки {file_path.name}: {e}")
			skipped += 1
			continue

		# Массовое сохранение (bulk)
		if save_to_db and use_bulk and bulk_buffer:
			with next(get_db()) as db:
				bulk_save_documents(db, bulk_buffer, update_mode=update_mode)

	# Итоговая статистика (общая)
	console.print("\n" + "=" * 50, style="dim")
	console.print(f"📊 Статистика обработки:", style="bold")
	console.print(f"   Всего документов: {len(files)}")
	console.print(f"   Обработано: {processed}")
	console.print(f"   Обновлено: {updated}")
	console.print(f"   Пропущено: {skipped}")
	console.print("=" * 50, style="dim")

	return processed


class DocumentParser:
	def parse_document(
			self,
			src: str,
			data: tuple[str, list[dict[str, Any]] | None],
			year: int
	) -> Optional['DocumentCreate']:
		try:
			# 1. Извлекаем текст и таблицы
			text, tables = data

			# 2. Парсим основные данные
			agreement_number = self._parse_agreement_number(text)
			agreement_year = self._parse_agreement_period(text)
			customers = self._parse_customers(text)
			allowed_deviation = self._parse_allowed_deviation(text)

			# 4. Парсим таблицы
			plans, validation_errors = self._prepare_plans(tables, customers, year)

			# 5. Валидация
			if not customers:
				validation_errors.append("Покупатель не определен")

			if not agreement_number:
				validation_errors.append("Не удалось определить номер соглашения")

			if not agreement_year:
				validation_errors.append("Период действия соглашения не определен")

			if not allowed_deviation:
				validation_errors.append("Не найдено минимально допустимое отклонение")

			if not plans:
				validation_errors.append(f"Не найдены планы закупок на {year} год")

			# 6. Возвращаем сформированный объект для сохранения
			return DocumentCreate(
				file_path=src,
				slug=slugify_filename(src),
				agreement_number=agreement_number or "* Без номера",
				customer_names=customers or ["* Без названия"],
				year=year,
				allowed_deviation=allowed_deviation or "* 0%",
				validation_errors=validation_errors,
				plans=plans
			)

		except Exception as e:
			return DocumentCreate(
				file_path=src,
				agreement_number="* Без номера",
				customer_names=["* Без названия"],
				year=get_current_year(),
				allowed_deviation="",
				validation_errors=[str(e)],
			)

	def _parse_customers(self, text: str) -> list[str] | None:
		"""
		Парсер который оставляет только короткие варианты названий.
		Учитывает случаи, когда правая скобка может отсутствовать:
		извлекает короткий вариант из круглой скобки до запятой/именуем.
		"""
		# 1. Ограничиваем поиск
		block_match = re.search(r'(.*?)(?=нижеследующем:|1\.)', text, re.DOTALL | re.IGNORECASE)
		if not block_match:
			return

		search_text = block_match.group(1)

		# 2. Объединяем переносы строк внутри кавычек
		search_text = re.sub(r'([«"\'`][^»"\'`]*)\n([^»"\'`]*[»"\'`])', r'\1 \2', search_text)

		# 3. Находим все организации, которые начинаются с формы юр.лица
		patterns = "|".join(re.escape(p) for p in settings.LEGAL_ENTITY_PATTERNS)

		# 4. Берём участок от формы организации компании до первой запятой или слова "именуем"
		regex = re.compile(rf'({patterns})([^,\n]*?)(?=[_,]|\bименуем\b)', re.IGNORECASE | re.DOTALL)
		matches = [m.group().strip() for m in regex.finditer(search_text)]

		# 5. Если есть скобки — берём последнюю часть (короткое имя), иначе само название
		customers = [part.strip(" )") for m in matches for part in [m.split("(")[-1].strip()]]

		# 6. Фильтруем исключения
		customers = [
			name for name in customers
			if not any(exc.lower() in name.lower() for exc in settings.EXCLUDE_NAME_LIST)
		]

		return customers

	def _parse_agreement_number(self, text: str) -> str | None:
		"""
		Ищет номер доп. Соглашения в начале строки с фразой 'ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ'.
		"""
		lines = text.split('\n')
		for line in lines:
			if line.strip().upper().startswith('ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ'):
				# Ищем номер после фразы
				match = re.search(r'ДОПОЛНИТЕЛЬНОЕ\s+СОГЛАШЕНИЕ\s*(?:№|No|#)?\s*(\S+)', line, re.IGNORECASE)
				if match:
					return match.group(1).strip()

	def _parse_agreement_period(self, text: str) -> str | None:
		"""
		Ищет годы из периода соглашения в блоке между пунктами 1. и 4.
		Возвращает последнее значение из найденных
		"""

		# Ищем блок между 1. и 2.
		block_match = re.search(r'1\.(.*?)4\.', text, re.DOTALL)
		if not block_match:
			return

		search_block = block_match.group(1)

		# Ищем все года в этом блоке
		year_matches = re.findall(r'20\d{2}', search_block)
		if year_matches:
			# Берем последнее вхождение
			return year_matches[-1]

	def _parse_allowed_deviation(self, text: str) -> str | None:
		"""
		Парсит допустимое отклонение из текстового блока между пунктами 4. и до конца.
		Берет последнее минимальное число, добавляет % если есть.
		Возвращает (минимальное отклонение, ошибки).
		"""

		block_match = re.search(r'4\..*?5\.', text, re.DOTALL)
		if not block_match:
			return None

		search_block = block_match.group(0)

		matches = re.findall(r'(\d+[.,]?\d*?)\s*(%|тонн)', search_block, re.DOTALL)
		if matches:
			number, unit = matches[-1]
			return f"{number.replace(',', '.')}{'%' if unit == '%' else 'т.'}"

		return None

	def _determine_customer_for_table(
			self,
			tables_count: int,
			table_index: int,
			customers: list[str]
	) -> tuple[Optional[str], list[str]]:
		"""
		Определяет покупателя для таблицы при условии нескольких таблиц.
		Возвращает: (имя покупателя, список ошибок)
		"""
		errors = []

		if tables_count == 1:
			# Одна таблица - для всех покупателей
			return None, errors

		if not customers:
			errors.append("Не определены покупатели для своих таблиц")
			return f"Покупатель_{table_index + 1}", errors

		# Несколько таблиц - назначаем по порядку (с начала)
		if table_index < len(customers):
			return customers[table_index], errors
		else:
			errors.append(f"Для таблицы {table_index + 1} не хватило покупателя (всего покупателей: {len(customers)})")
			return None, errors  # Возвращаем None если не хватило покупателя

	def _prepare_plans(
			self,
			tables: list[list[list[str]]] | None,
			customers: list[str],
			year: int
	) -> tuple[list[ProductPlanCreate] | None, list[str] | None]:
		"""
		Извлекает итоговые значения по месяцам из структурированных таблиц и формирует объекты планов.
		Если покупателей несколько и таблиц тоже, то закрепляются планы за каждым покупателем.
		Возвращает: (список объектов ProductPlanCreate для всех 12 месяцев, список ошибок)
		"""
		if not tables:
			return None, None

		all_plans = []
		all_errors = []

		for i, table in enumerate(tables):
			# Определяем покупателя для таблицы если несколько таблиц
			customer_name, errors = self._determine_customer_for_table(len(tables), i, customers)
			all_errors.extend(errors)

			monthly_totals = {month: 0.0 for month in range(1, 13)}

			for row in table[1:]:  # Пропускаем шапку
				if not row or len(row) < 2:
					continue

				date_str = row[0]
				try:
					month_num = int(date_str.split('.')[0])
					date_year = int(date_str.split('.')[1])

					if date_year != year or not 1 <= month_num <= 12:
						continue

					total_str = row[-1] or "0"
					total_value = float(total_str.replace(',', '.').replace(' ', ''))
					monthly_totals[month_num] = total_value

				except (ValueError, IndexError):
					continue

			# Создаем объект "планы закупок" для этого покупателя
			customer_plans = [
				ProductPlanCreate(
					month=month,
					year=year,
					planned_quantity=monthly_totals[month],
					customer_name=customer_name,
				)
				for month in range(1, 13)
			]

			all_plans.extend(customer_plans)

		return all_plans, all_errors

	@staticmethod
	def format_status(validation_errors: list[str], is_exist: bool, update_mode: bool) -> str:
		"""Формирует статус для вывода в консоль"""

		# Валидация
		if validation_errors:
			validation = f"[red]{len(validation_errors)} ошибка[/red]"
		else:
			validation = "[green]OK[/green]"

		if is_exist:
			if update_mode:
				action = " ([blue]Обновлен[/blue])"
			else:
				action = " ([yellow]Пропущен[/yellow])"
		else:
			action = ""

		return f"{validation} {action}"
