import re
from pathlib import Path
from typing import Optional, Any

from app.models import DocumentCreate, ProductPlanCreate
from app.services.utils import get_current_year, extract_tables_from_pdf, extract_text_from_pdf


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

	def parse_document(self, file_path: Path) -> Optional[DocumentCreate]:
		try:
			validation_errors = []
			plans = []

			# 1. Извлекаем текст
			text = extract_text_from_pdf(str(file_path))
			if not text:
				return None

			# 2. Парсим основные данные
			agreement_number = self._parse_agreement_number(text)
			customers = self._parse_customers(text)
			year_str = self._detect_year(text)

			try:
				year = int(re.sub(r'\D', '', year_str)[:4])
				if year < 2000 or year > 2100:
					year = get_current_year()
			except:
				year = get_current_year()

			# 3. Парсим допустимое отклонение с обработкой ошибок
			allowed_deviation, deviation_errors = self._parse_allowed_deviation(text)

			# 4. Извлекаем и парсим таблицы
			raw_tables = extract_tables_from_pdf(str(file_path))

			for i, table in enumerate(raw_tables):
				if not table or len(table) < 2:
					continue

				# Определяем покупателя для найденных таблиц с обработкой ошибок
				customer_name, customer_errors = self._determine_customer_for_table(
					tables_count=len(raw_tables),
					table_index=i,
					customers=customers
				)

				validation_errors.extend(customer_errors)

				table_plans = self._parse_table_data(table, year, customer_name)
				plans.extend(table_plans)

			# 5. Валидация
			if agreement_number == "* без номера":
				validation_errors.append("Не удалось определить номер соглашения")
			if not plans:
				validation_errors.append("Не найдены данные о планах поставок")
			if isinstance(year_str, str) and year_str.startswith('*'):
				validation_errors.append("Год определен по умолчанию")

			# 6. Создаем результат
			return DocumentCreate(
				file_path=str(file_path),
				agreement_number=agreement_number,
				customer_names=customers,
				year=year,
				allowed_deviation=allowed_deviation,  # ← Теперь здесь!
				validation_errors=validation_errors,
				plans=plans
			)

		except Exception as e:
			return DocumentCreate(
				file_path=str(file_path),
				agreement_number="* ошибка парсинга",
				customer_names=["* ошибка парсинга"],
				year=get_current_year(),
				allowed_deviation="* 0",
				validation_errors=[f"Ошибка: {str(e)}"],
				plans=[]
			)

	def _parse_customers(self, text: str) -> list[str]:
		"""
		Парсит всех покупателей с учетом исключений.
		"""
		from app.config import settings

		customers = []

		# Ищем блок до пункта "1."
		block_match = re.search(r'(.*?)(?=1\.)', text, re.DOTALL)
		if not block_match:
			return ["* без названия"]

		search_block = block_match.group(1)

		# Создаем динамический паттерн
		patterns = "|".join(re.escape(pattern) for pattern in settings.LEGAL_ENTITY_PATTERNS)
		pattern = rf'((?:{patterns})[^,]+?)(?=,|\n|именуемое)'

		matches = re.finditer(pattern, search_block, re.IGNORECASE)

		for match in matches:
			customer = match.group(1).strip()

			# Очищаем
			customer = re.sub(r'^[\s_]+|[\s_]+$', '', customer)

			# Убираем лишние скобки и кавычки
			customer = re.sub(r'\([^)]*\)', '', customer)  # Убираем (ООО «Ромашка»)
			customer = re.sub(r'"[^"]*"', '', customer)  # Убираем "ООО Ромашка"
			customer = customer.strip()

			# Проверяем исключения
			should_exclude = any(
				exclude_term.lower() in customer.lower()
				for exclude_term in settings.EXCLUDE_NAME_LIST
			)

			# Дополнительная проверка длины
			is_valid_length = 5 < len(customer) < 200

			if customer and not should_exclude and is_valid_length:
				customers.append(customer)

		# Убираем дубликаты
		unique_customers = []
		for customer in customers:
			if customer not in unique_customers:
				unique_customers.append(customer)

		if not unique_customers:
			return ["* без названия"]

		return unique_customers

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
		Находит все таблицы между пунктами 2. и 3.
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

	def _parse_date_with_year(self, cell: str, document_year: int) -> tuple[Optional[int], int]:
		"""
		Парсит дату и возвращает месяц и найденный год.
		Проверяет соответствие году документа.
		"""
		cell_lower = cell.lower().strip()
		found_year = document_year  # По умолчанию используем год документа

		# Сначала пытаемся извлечь год из ячейки
		year_match = re.search(r'20\d{2}', cell_lower)
		if year_match:
			found_year = int(year_match.group())

		# Если найденный год не совпадает с годом документа - пропускаем
		if found_year != document_year:
			return None, found_year

		# Теперь парсим месяц (упрощенная версия без дублирования года)
		# Формат: Январь, Апрель, апрель
		for month_name, month_num in self.month_map.items():
			if month_name in cell_lower:
				return month_num, found_year

		# Формат: янв., фев., мар.
		month_abbr_map = {
			'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
			'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
		}

		for abbr, month_num in month_abbr_map.items():
			if abbr in cell_lower:
				return month_num, found_year

		# Формат: 01 или 1 (только месяц)
		month_match = re.search(r'\b([1-9]|1[0-2])\b', cell_lower)
		if month_match:
			try:
				month = int(month_match.group(1))
				if 1 <= month <= 12:
					return month, found_year
			except ValueError:
				pass

		return None, found_year

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

	def _extract_product_names(self, header_row: list[str]) -> list[str]:
		"""
		Извлекает названия продуктов из заголовка таблицы.
		"""
		product_names = []

		for i, cell in enumerate(header_row):
			if i == 0:
				continue  # Пропускаем первую колонку (обычно "Месяц")

			# Очищаем название от единиц измерения и лишних слов
			name = re.sub(r'\(.*?\)|тонн|т\.|т\b', '', cell, flags=re.IGNORECASE).strip()
			if name:
				product_names.append(name)
			else:
				product_names.append(f"Продукт {i}")

		return product_names

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

	def _detect_year(self, text: str) -> str | Any:
		"""
		Ищет год в блоке между 1. и 2.
		Берет последнее вхождение, иначе текущий год с '*'.
		"""

		# Ищем блок между 1. и 2.
		block_match = re.search(r'1\.(.*?)2\.', text, re.DOTALL)
		if not block_match:
			return f"* {get_current_year()}"

		search_block = block_match.group(1)

		# Ищем все года в этом блоке
		year_matches = re.findall(r'20\d{2}', search_block)
		if year_matches:
			# Берем последнее вхождение
			return year_matches[-1]
		else:
			return f"* {get_current_year()}"

	def _parse_agreement_number(self, text: str) -> str:
		"""
		Ищет номер доп. Соглашения в начале строки с фразой 'ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ'.
		Возвращает "* без номера" если не найдено.
		"""
		lines = text.split('\n')
		for line in lines:
			if line.strip().upper().startswith('ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ'):
				# Ищем номер после фразы
				match = re.search(r'ДОПОЛНИТЕЛЬНОЕ\s+СОГЛАШЕНИЕ\s*(?:№|No|#)?\s*(\S+)', line, re.IGNORECASE)
				if match:
					return match.group(1).strip()
				else:
					# Если фраза есть, но номера нет
					return "* без номера"
		return "* без номера"

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

	def _parse_allowed_deviation(self, text: str)  -> tuple[Optional[str], list[str]]:
		"""
		Парсит допустимое отклонение из блока между 4. и 5.
		Берет последнее число, добавляет % если есть.
		Возвращает (отклонение, ошибки).
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


def parse_document_file(file_path: Path) -> Optional[DocumentCreate]:
	"""
	Публичная функция для парсинга файла документа.
	Используется внешними модулями для обработки файлов.

	Args:
		file_path: Путь к файлу для парсинга

	Returns:
		DocumentCreate или None в случае ошибки
	"""
	parser = DocumentParser()
	return parser.parse_document(file_path)
