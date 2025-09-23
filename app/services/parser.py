import re
from pathlib import Path
from typing import Optional, Any

from app.config import settings
from app.crud import create_document, update_document, get_document_by_file_path, bulk_save_documents
from app.db import get_db
from app.models import DocumentCreate, ProductPlanCreate
from app.utils.base import get_current_year, extract_data_from_file, format_string_list
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
			data = extract_data_from_file(file_path)
			if not data[0]:
				continue

			# Парсим документы за указанный год
			document_data = parser.parse_document(str(file_path.name), data=data, year=year)

			# Фильтр по году
			if not document_data.plans:
				full_status = parser.format_status(document_data.validation_errors, True, False)
				console.print(f"[{i:03d}/{len(files)}]: [grey]{file_path.name}[/grey] ... {full_status}")
				continue

			with next(get_db()) as db:
				existing_doc = get_document_by_file_path(db, str(file_path))

				if existing_doc:
					if update_mode:
						if save_to_db and not use_bulk:
							document_data = update_document(db, existing_doc.id, document_data)
						updated += 1
					else:
						skipped += 1
						full_status = parser.format_status(document_data.validation_errors, True, update_mode)
						console.print(f"[{i:03d}/{len(files)}]: [grey]{file_path.name}[/grey] ... {full_status}")
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
	def __init__(self):
		self.pattern_table_header = re.compile(
			r'срок\s*\(период\)\s*поставки|месяц/год|продукт',
			re.IGNORECASE
		)
		self.month_map = {
			'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
			'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
			'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
		}

	def parse_document(
			self,
			src: str,
			data: tuple[str, list[dict[str, Any]] | None],
			year: int
	) -> Optional[DocumentCreate]:
		try:
			validation_errors = []
			plans = []

			# 1. Извлекаем текст и таблицы
			text, tables = data

			# 2. Парсим основные данные
			agreement_number = self._parse_agreement_number(text)
			agreement_year = self._parse_agreement_period(text)
			customers = self._parse_customers(text)

			# 3. Парсим допустимое отклонение с обработкой ошибок
			allowed_deviation, deviation_errors = self._parse_allowed_deviation(text)

			# 4. Парсим таблицы
			for i, table in enumerate(tables):
				if not table or len(table) < 2:
					continue

				# Определяем покупателя для найденных таблиц с обработкой ошибок
				customer_name, customer_errors = self._determine_customer_for_table(
					tables_count=len(tables),
					table_index=i,
					customers=customers
				)

				validation_errors.extend(customer_errors)

				table_data = table.get('data')
				if table_data:
					table_plans = self._parse_table_data(table_data, year, customer_name)
					plans.extend(table_plans)

			# 5. Валидация
			if not customers:
				validation_errors.append("Покупатель не определен")

			if not agreement_number:
				validation_errors.append("Не удалось определить номер соглашения")

			if not agreement_year:
				validation_errors.append("Год окончания действия соглашения не определен")

			if not plans:
				validation_errors.append(f"Не найдены таблицы с планами закупок на {year} год")

			# 6. Возвращаем сформированный объект для сохранения
			return DocumentCreate(
				file_path=src,
				agreement_number=agreement_number or "* Без номера",
				customer_names=customers or ["* Без названия"],
				year=year,
				allowed_deviation=allowed_deviation,
				validation_errors=validation_errors,
				plans=plans
			)

		except Exception as e:
			return DocumentCreate(
				file_path=src,
				agreement_number="* ошибка парсинга",
				customer_names=["* ошибка парсинга"],
				year=get_current_year(),
				allowed_deviation="* 0",
				validation_errors=[str(e)],
				plans=[]
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

		# 3. Юр. формы
		patterns = "|".join(re.escape(p) for p in settings.LEGAL_ENTITY_PATTERNS)

		# 4. Берём участок от юр.формы до первой запятой или слова "именуем"
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

	def _determine_customer_for_table(
			self,
			tables_count: int,
			table_index: int,
			customers: list[str]
	) -> tuple[Optional[str], list[str]]:
		"""
		Определяет покупателя для таблицы с обработкой ошибок.
		"""
		errors = []

		if tables_count == 1:
			# Одна таблица - для всех покупателей
			return None, errors

		# Несколько таблиц - назначаем по порядку
		customer_idx = min(table_index, len(customers) - 1)

		if customers and customer_idx < len(customers):
			return customers[customer_idx], errors
		else:
			# Неизвестный покупатель
			customer_name = f"* Покупатель {table_index + 1}"
			errors.append(f"Неизвестный покупатель для таблицы {table_index + 1}")
			return customer_name, errors

	def _parse_tables_to_plans(self, tables: list[list[list[str]]], year: int, customers: list[str]) -> list[
		ProductPlanCreate]:
		"""
		Парсит таблицы и создает планы с группировкой по покупателям.
		"""
		plans = []

		for i, table in enumerate(tables):
			if not table or len(table) < 2:
				continue

			# Определяем покупателя для этой таблицы
			if len(tables) == 1:
				# Если одна таблица - не указываем конкретного покупателя
				customer_name = None
			else:
				# Если несколько таблиц - назначаем по порядку
				customer_idx = min(i, len(customers) - 1)
				customer_name = customers[customer_idx] if customers else f"неизвестный покупатель {i + 1}"

			table_plans = self._parse_table_data(table, year, customer_name)
			plans.extend(table_plans)

		return plans

	def _find_all_tables(self, text: str) -> list[list[list[str]]]:
		"""
		Находит все таблицы в тексте документа между пунктами 2. и 3.
		TODO: склеить таблицы, если это одна резаная на две страницы. То есть в первой ячейке первой строки не может быть число в новой таблице!
		"""
		tables = []

		# Ищем все блоки между 2. и 3.
		table_blocks = re.findall(r'2\.(.*?)3\.', text, re.DOTALL | re.IGNORECASE)

		for block in table_blocks:
			table = self._extract_table_from_block(block)
			if table and len(table) > 1:  # Таблица должна иметь заголовок и данные
				tables.append(table)

		return tables

	def _parse_table_data(
			self,
			table: list[list[str]],
			year: int,
			customer_name: str
	) -> list[ProductPlanCreate]:
		"""
		Парсит таблицу и суммирует все значения по месяцам.
		"""
		plans = []

		if not table or len(table) < 2:
			return plans

		# Обрабатываем строки данных (пропускаем заголовок)
		for row in table[1:]:
			if not row or not any(cell.strip() for cell in row):
				continue

			# Парсим месяц из первой колонки
			month = self._parse_month_from_cell(row[0], year)
			if month is None:
				continue

			# Суммируем все числовые значения в строке
			total_quantity = 0
			for quantity_str in row[1:]:
				quantity = self._parse_quantity(quantity_str)
				if quantity is not None:
					total_quantity += quantity

			if total_quantity > 0:
				plans.append(ProductPlanCreate(
					month=month,
					year=year,
					planned_quantity=total_quantity,
					customer_name=customer_name,
				))

		return plans

	def _process_numeric_columns(self, cells: list[str], product_names: list[str]) -> list[tuple[str, Optional[float]]]:
		"""
		Обрабатывает числовые колонки с проверкой условий суммирования.
		"""
		quantities = []
		numeric_values = []

		# Парсим все числовые значения
		for cell in cells:
			quantity = self._parse_quantity(cell)
			numeric_values.append(quantity)

		if not numeric_values:
			return []

		# Проверяем условие суммирования
		should_skip_last = self._should_skip_last_column(numeric_values)

		# Формируем результат
		for i, quantity in enumerate(numeric_values):
			if should_skip_last and i == len(numeric_values) - 1:
				continue  # Пропускаем последнюю колонку

			product_idx = min(i, len(product_names) - 1)
			product_name = product_names[product_idx] if product_names else f"Продукт {i + 1}"

			quantities.append((product_name, quantity))

		return quantities

	def _should_skip_last_column(self, values: list[Optional[float]]) -> bool:
		"""
		Проверяет условия для пропуска последней колонки.
		"""
		if len(values) <= 1:
			return False

		# Фильтруем None значения
		valid_values = [v for v in values if v is not None]

		if len(valid_values) < 2:
			return False

		# Суммируем все значения кроме последнего
		sum_without_last = sum(valid_values[:-1])
		last_value = valid_values[-1]

		# Условие 1: сумма не равна нулю
		if sum_without_last == 0:
			return False

		# Условие 2: сумма равна последнему значению (с учетом округления)
		is_equal = abs(sum_without_last - last_value) < 0.01  # Допуск для float

		# Условие 3: целые части равны (для случаев без дробной части)
		is_int_equal = (int(sum_without_last) == int(last_value)) if all(v == int(v) for v in valid_values) else False

		# Условие 4: больше одной колонки с числами
		has_multiple_columns = len(valid_values) > 1

		return (is_equal or is_int_equal) and has_multiple_columns

	def _extract_table(self, lines: list[str], start_idx: int) -> list[list[str]]:
		"""
		Извлекает таблицу из текста, начиная с указанной строки.
		Возвращает список строк таблицы, где каждая строка - список ячеек.
		"""
		table = []
		i = start_idx

		# Добавляем заголовок таблицы
		header = self._split_table_row(lines[i])
		if header:
			table.append(header)
			i += 1

		# Извлекаем строки таблицы пока находим данные
		while i < len(lines):
			line = lines[i].strip()
			if not line:
				i += 1
				continue

			# Проверяем, является ли строка частью таблицы (содержит числа или месяцы)
			if self._is_table_row(line):
				row = self._split_table_row(line)
				if row:
					table.append(row)
				i += 1
			else:
				# Если нашли не табличную строку - заканчиваем извлечение
				break

		return table if len(table) > 1 else []  # Возвращаем только если есть данные

	def _extract_table_from_block(self, block: str) -> list[list[str]]:
		"""
		Извлекает таблицу из текстового блока.
		"""
		table = []
		lines = block.split('\n')

		for line in lines:
			line = line.strip()
			if not line:
				continue

			# Разбиваем строку на ячейки (учитываем различные разделители)
			cells = self._split_table_row(line)
			if cells:
				table.append(cells)

		return table

	def _split_table_row(self, line: str) -> list[str]:
		"""
		Улучшенная разбивка строки таблицы на ячейки.
		Учитывает различные разделители и форматирование.
		"""
		# Заменяем различные разделители на единый
		normalized_line = re.sub(r'[|\t;]+', '  ', line.strip())

		# Разбиваем по 2+ пробелам (учитываем выравнивание таблицы)
		cells = re.split(r'\s{2,}', normalized_line)

		# Очищаем и фильтруем ячейки
		cleaned_cells = []
		for cell in cells:
			cell = cell.strip()
			# Убираем лишние символы вокруг чисел
			cell = re.sub(r'^\D*|\D*$', '', cell)
			if cell:
				cleaned_cells.append(cell)

		return cleaned_cells

	def _is_table_row(self, line: str) -> bool:
		"""
		Проверяет, является ли строка строкой таблицы.
		Ищет числа, названия месяцев или типичные шаблоны табличных данных.
		"""
		# Проверяем на наличие чисел
		has_numbers = bool(re.search(r'\d', line))
		# Проверяем на наличие месяцев
		has_months = any(month in line.lower() for month in self.month_map.keys())
		# Проверяем на типичные табличные паттерны
		has_table_pattern = bool(re.search(r'.*\d.*\d.*\d', line))  # Хотя бы 3 числа в строке

		return has_numbers or has_months or has_table_pattern

	def _parse_month_from_cell(self, cell: str, year: int) -> Optional[int]:
		"""
		Парсит месяц из ячейки с использованием переданного года.
		"""
		cell_lower = cell.lower().strip()

		# Формат: Январь get_current_year(), Апрель 2025г., апрель 2025г.
		for month_name, month_num in self.month_map.items():
			if month_name in cell_lower:
				# Проверяем соответствие года в ячейке и переданного года
				year_match = re.search(r'20\d{2}\s*г?\.?', cell_lower)
				if year_match:
					year_str = re.sub(r'\D', '', year_match.group())
					cell_year = int(year_str) if year_str else year
					if cell_year != year:
						return None  # Год не совпадает - пропускаем
				return month_num

		# Формат: янв., фев.
		month_abbr_map = {
			'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
			'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
		}

		for abbr, month_num in month_abbr_map.items():
			if abbr in cell_lower:
				return month_num

		# Формат: 01 или 1
		month_match = re.search(r'\b([1-9]|1[0-2])\b', cell_lower)
		if month_match:
			try:
				month = int(month_match.group(1))
				if 1 <= month <= 12:
					return month
			except ValueError:
				pass

		return None

	def _parse_quantity(self, quantity_str: str) -> Optional[float]:
		"""
		Парсит количество из строки, обрабатывая различные форматы.
		"""
		if not quantity_str or quantity_str.strip() == '':
			return None

		try:
			# Убираем все нечисловые символы кроме точки, запятой и минуса
			cleaned = re.sub(r'[^\d,.\-]', '', quantity_str.replace(' ', ''))

			# Заменяем запятую на точку для float преобразования
			cleaned = cleaned.replace(',', '.')

			# Если строка пустая после очистки
			if not cleaned:
				return None

			return float(cleaned)
		except (ValueError, TypeError):
			return None

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
		Ищет годы из периода соглашения в блоке между пунктами 1. и 2.
		Возвращает последнее значение из найденных
		"""

		# Ищем блок между 1. и 2.
		block_match = re.search(r'1\.(.*?)2\.', text, re.DOTALL)
		if not block_match:
			return

		search_block = block_match.group(1)

		# Ищем все года в этом блоке
		year_matches = re.findall(r'20\d{2}', search_block)
		if year_matches:
			# Берем последнее вхождение
			return year_matches[-1]

	def _find_table_by_pattern(self, text: str, pattern: str) -> Optional[list[list[str]]]:
		"""
		Находит таблицу по определенному шаблону.
		"""
		lines = text.split('\n')
		for i, line in enumerate(lines):
			if re.search(pattern, line, re.IGNORECASE):
				table = self._extract_table(lines, i)
				if table:
					return table
		return None

	def _parse_allowed_deviation(self, text: str) -> tuple[Optional[str], list[str]]:
		"""
		Парсит допустимое отклонение из текстового блока между пунктами 4. и 5.
		Берет последнее минимальное число, добавляет % если есть.
		Возвращает (минимальное отклонение, ошибки).
		"""
		validation_errors = []

		# Ищем блок между 4. и 5.
		block_match = re.search(r'4\.(.*?)5\.', text, re.DOTALL | re.IGNORECASE)
		if not block_match:
			validation_errors.append("Не найдено допустимое отклонение")
			return "* 0", validation_errors

		search_block = block_match.group(1)

		# Ищем все числа с возможными процентами
		deviation_pattern = r'(\d+)\s*%?'
		matches = re.findall(deviation_pattern, search_block)

		if not matches:
			validation_errors.append("Не найдено допустимое отклонение")
			return "* 0", validation_errors

		# Берем последнее число
		last_number = matches[-1]

		# Проверяем, есть ли знак процента после числа
		percent_match = re.search(r'{}\s*%'.format(re.escape(last_number)), search_block)
		if percent_match:
			return f"{last_number}%", validation_errors
		else:
			return last_number, validation_errors

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
