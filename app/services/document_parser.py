import re
from typing import Optional
from pathlib import Path
from .utils import parse_file_to_text
from app.models import DocumentCreate, ProductPlanCreate


class DocumentParser:
	def __init__(self):
		# Регулярные выражения для парсинга
		self.pattern_agreement_num = re.compile(
			r'соглашение\s*(?:№|n|#)?\s*(\S+)',
			re.IGNORECASE
		)
		self.pattern_customer = re.compile(
			r'«([^»]+)»[^,]*именуемое[^,]*«Покупатель',
			re.IGNORECASE
		)

		self.month_map = {
			'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
			'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
			'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
		}

	def parse_document(self, file_path: Path) -> Optional[DocumentCreate]:
		"""
		Основной метод парсинга документа.
		"""
		try:
			# Извлекаем текст используя универсальный парсер
			text = parse_file_to_text(file_path)
			if not text:
				return None

			text_lower = text.lower()
			validation_errors = []

			# Парсим основные данные
			agreement_number = self._parse_agreement_number(text_lower)
			customer_name = self._parse_customer(text_lower)

			# Парсим таблицу с планами
			product_plans = self._parse_product_table(text)

			# Валидация
			if not agreement_number:
				validation_errors.append("Не удалось определить номер соглашения")
			if not customer_name:
				validation_errors.append("Не удалось определить покупателя")
			if not product_plans:
				validation_errors.append("Не найдены табличные данные с помесячными планами закупок")

			# Создаем объект данных
			return DocumentCreate(
				file_path=str(file_path),
				agreement_number=agreement_number,
				customer_name=customer_name,
				validation_errors=validation_errors,
				product_plans=product_plans
			)

		except Exception as e:
			# Логируем ошибку, но не прерываем выполнение
			print(f"Ошибка при парсинге документа {file_path}: {e}")
			return DocumentCreate(
				file_path=str(file_path),
				validation_errors=[f"Ошибка парсинга: {str(e)}"],
				product_plans=[]
			)

	def _parse_agreement_number(self, text: str) -> Optional[str]:
		"""Парсит номер соглашения."""
		match = self.pattern_agreement_num.search(text)
		if match:
			# Очищаем номер от лишних символов
			number = re.sub(r'[\s«»"()]', '', match.group(1))
			return number
		return None

	def _parse_customer(self, text: str) -> Optional[str]:
		"""Парсит название покупателя."""
		match = self.pattern_customer.search(text)
		if match:
			return f"ООО «{match.group(1)}»"
		return None

	def _parse_product_table(self, text: str) -> list[ProductPlanCreate]:
		"""
		Парсит таблицу с месячными планами поставок.
		"""
		plans = []
		lines = text.split('\n')
		current_year = self._detect_year(text) or 2025

		# Сначала пытаемся определить названия продуктов из заголовков таблицы
		product_names = self._detect_product_names(text)

		for i, line in enumerate(lines):
			line_lower = line.lower()

			# Ищем строки с названиями месяцев
			for month_name, month_num in self.month_map.items():
				if month_name in line_lower:
					# Ищем числовые данные в этой и следующих строках
					quantities = self._extract_quantities_from_context(lines, i)

					# Создаем записи для каждого продукта
					for product_idx, quantity in enumerate(quantities):
						if quantity is not None:
							product_name = product_names[product_idx] if product_idx < len(
								product_names) else f"Продукт {product_idx + 1}"

							plans.append(ProductPlanCreate(
								product_name=product_name,
								month=month_num,
								year=current_year,
								planned_quantity=quantity
							))

		return plans

	def _detect_year(self, text: str) -> Optional[int]:
		"""Определяет год из текста документа."""
		year_match = re.search(r'20\d{2}', text)
		if year_match:
			try:
				return int(year_match.group())
			except ValueError:
				pass
		return None

	def _detect_product_names(self, text: str) -> list[str]:
		"""Пытается определить названия продуктов из заголовков таблицы."""
		lines = text.split('\n')
		product_names = []

		# Ищем строку с заголовками таблицы
		for line in lines:
			if any(keyword in line.lower() for keyword in ['продукт', 'тонн', 'т.']):
				# Разбиваем на колонки и берем все, кроме первой (месяц)
				columns = re.split(r'\s{2,}', line.strip())
				if len(columns) > 1:
					product_names = [col.strip() for col in columns[1:]]
					break

		return product_names or ["Продукт 1", "Продукт 2"]

	def _extract_quantities_from_context(self, lines: list[str], line_idx: int) -> list[Optional[float]]:
		"""
		Извлекает количества из контекста вокруг строки с месяцем.
		"""
		quantities = []

		# Проверяем текущую строку и следующие 2 строки
		for i in range(line_idx, min(line_idx + 3, len(lines))):
			numbers = self._extract_numbers_from_line(lines[i])
			if numbers:
				quantities.extend(numbers)
				break

		return quantities

	def _extract_numbers_from_line(self, line: str) -> list[Optional[float]]:
		"""
		Извлекает числа из строки, обрабатывая различные форматы.
		"""
		numbers = []
		# Ищем все возможные числовые форматы (включая десятичные)
		number_matches = re.findall(r'\b\d+[\s,]*\d*[.,]?\d*\b', line)

		for match in number_matches:
			try:
				# Заменяем запятые на точки и убираем пробелы
				cleaned = match.replace(',', '.').replace(' ', '')
				numbers.append(float(cleaned))
			except ValueError:
				numbers.append(None)

		return numbers


# Функция для использования в других модулях
def parse_document_file(file_path: Path) -> Optional[DocumentCreate]:
	"""
	Парсит файл документа и возвращает структурированные данные.
	"""
	parser = DocumentParser()
	return parser.parse_document(file_path)
