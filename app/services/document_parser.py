import re
from pathlib import Path
from typing import Optional, Any

from app.models import DocumentCreate, ProductPlanCreate
from app.services.utils import parse_file_to_text, get_current_year


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
		"""
		Основной метод парсинга с обработкой ошибок и логированием.
		"""
		try:
			text = parse_file_to_text(file_path)
			if not text or len(text.strip()) < 50:  # Минимальная длина текста
				print(f"Файл {file_path.name} содержит слишком мало текста или пуст")
				return None

			# Парсим основные данные по новым правилам
			agreement_number = self._parse_agreement_number(text)
			customers = self._parse_customers(text)
			year_str = self._detect_year(text)

			# Преобразуем год в int если возможно (убираем '*' для преобразования)
			try:
				year = int(re.sub(r'\D', '', year_str)[:4])  # Обеспечиваем 4 цифры
				if year < 2000 or year > 2100:  # Валидация диапазона
					year = get_current_year()
			except (ValueError, IndexError):
				year = get_current_year()

			if not customers:
				print(f"Не найдены покупатели в файле {file_path.name}")

			# Находим все таблицы
			tables = self._find_all_tables(text)

			# Распределяем таблицы (передаем год как параметр)
			product_plans = self._assign_tables_to_customers(tables, customers, text, year)

			# Валидация и создание результата
			validation_errors = []

			# Проверяем наличие номера соглашения (учитываем, что теперь всегда возвращается строка)
			if agreement_number == "* без номера":
				validation_errors.append("Не удалось определить номер соглашения")

			if not product_plans:
				validation_errors.append("Не найдены данные о планах поставок")

			# Проверяем год на наличие '*' (означает, что год определен по умолчанию)
			if isinstance(year_str, str) and year_str.startswith('*'):
				validation_errors.append("Год определен по умолчанию")

			result = DocumentCreate(
				file_path=str(file_path),
				agreement_number=agreement_number,
				year=year,
				customer_names=customers,
				validation_errors=validation_errors,
				product_plans=product_plans
			)

			return result

		except Exception as e:
			print(f"Критическая ошибка при парсинге {file_path.name}: {e}")
			import traceback
			traceback.print_exc()

			return DocumentCreate(
				file_path=str(file_path),
				agreement_number="* ошибка парсинга",
				year=get_current_year(),
				customer_names=["* ошибка парсинга"],
				validation_errors=[f"Критическая ошибка парсинга: {str(e)}"],
				product_plans=[]
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

	def _assign_tables_to_customers(self, tables: list, customers: list[str], text: str, year: int) -> list[
		ProductPlanCreate]:
		"""
		Распределяет таблицы по покупателям согласно алгоритму с учетом отклонений.

		Args:
			tables: список найденных таблиц
			customers: список покупателей
			text: исходный текст для дополнительного анализа
			year: год для планов поставок
		"""
		plans = []
		validation_errors = []

		# Алгоритм распределения
		if not customers:
			return plans

		if not tables:
			return plans

		# Парсим отклонения ДО распределения таблиц
		deviations, deviation_errors = self._parse_allowed_deviations(text, len(tables))
		validation_errors.extend(deviation_errors)

		# Распределяем таблицы покупателям
		assigned_tables = {}
		for i, table in enumerate(tables):
			customer_idx = min(i, len(customers) - 1)
			customer_name = customers[customer_idx]

			# Получаем отклонение для этой таблицы (если есть)
			deviation = deviations[i] if i < len(deviations) else None

			if customer_name not in assigned_tables:
				assigned_tables[customer_name] = []
			assigned_tables[customer_name].append((table, deviation))

		# Если покупателей больше чем таблиц - объединяем лишних с последним
		if len(customers) > len(tables):
			last_customer = customers[len(tables) - 1]
			for extra_customer in customers[len(tables):]:
				# Объединяем имена
				merged_name = f"{last_customer} и {extra_customer}"
				if merged_name in assigned_tables:
					# Переименовываем существующие записи
					for plan in plans:
						if plan.customer_name == last_customer:
							plan.customer_name = merged_name
					last_customer = merged_name

		# Парсим таблицы и создаем планы с отклонениями
		for customer_name, table_data in assigned_tables.items():
			for table, deviation in table_data:
				table_plans = self._parse_table_data(table, year, customer_name, deviation)
				plans.extend(table_plans)

		return plans

	def _parse_table_data(
			self,
			table: list[list[str]],
			year: int,
			customer_name: str,
			deviation: Optional[str]
	) -> list[ProductPlanCreate]:
		"""
		Парсит данные таблицы с проверкой года.
		"""
		plans = []

		if not table or len(table) < 2:
			return plans

		product_names = self._extract_product_names(table[0])

		for row in table[1:]:
			if not row:
				continue

			# Используем функцию для парсинга даты с проверкой года
			month, found_year = self._parse_date_with_year(row[0], year)
			if month is None:
				continue  # Пропускаем строки без валидного месяца

			# Проверяем соответствие года документа
			if found_year != year:
				continue  # Пропускаем строки с несоответствующим годом

			# Обрабатываем числовые колонки
			quantities = self._process_numeric_columns(row[1:], product_names)

			for product_name, quantity in quantities:
				if quantity is not None:
					plans.append(ProductPlanCreate(
						product_name=product_name,
						month=month,
						year=found_year,
						planned_quantity=quantity,
						allowed_deviation=deviation,
						customer_name=customer_name
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

	def _parse_month_from_cell(self, cell: str) -> Optional[int]:
		"""
		Парсит только месяц из ячейки (без учета года).
		Используется в других местах, где год не важен.
		"""
		cell_lower = cell.lower().strip()

		# Формат: Январь, Апрель
		for month_name, month_num in self.month_map.items():
			if month_name in cell_lower:
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

	def _parse_allowed_deviations(self, text: str, tables_count: int) -> tuple[list[str], list[str]]:
		"""
		Парсит допустимые отклонения из блока между 4. и 5.
		Возвращает список отклонений и ошибки валидации.
		"""
		validation_errors = []

		# Ищем блок между 4. и 5.
		block_match = re.search(r'4\.(.*?)5\.', text, re.DOTALL | re.IGNORECASE)
		if not block_match:
			return [], validation_errors

		search_block = block_match.group(1)

		# Ищем все числа в блоке
		numbers = []
		number_pattern = r'\b\d+[\d,.]*\d*\b'
		matches = re.finditer(number_pattern, search_block)

		for match in matches:
			number_str = match.group()
			# Проверяем, есть ли после числа символ %
			next_char = search_block[match.end()] if match.end() < len(search_block) else ''
			if next_char == '%':
				number_str += '%'
			numbers.append(number_str)

		if not numbers:
			return [], validation_errors

		# Распределяем отклонения по таблицам
		if tables_count == 0:
			return [], validation_errors

		if len(numbers) == 1:
			# Одно число на все таблицы
			deviations = [numbers[0]] * tables_count

		elif len(numbers) == tables_count:
			# Количество таблиц совпадает с найденным количеством чисел отклонений
			deviations = numbers

		elif len(numbers) > tables_count:
			# Числ больше чем таблиц - берем последние numbers
			deviations = numbers[-tables_count:]
			# Помечаем звездочкой и добавляем ошибку
			deviations = [f"* {dev}" for dev in deviations]
			validation_errors.append("отклонение требует ручной проверки")

		else:  # len(numbers) < tables_count
			# Числ меньше чем таблиц - повторяем последнее число
			last_number = numbers[-1]
			deviations = [last_number] * tables_count

		return deviations, validation_errors


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
