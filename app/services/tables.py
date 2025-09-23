import re
from typing import Any


def clean_table_data(table: list[list[Any]]) -> list[list[str]]:
	"""
	Очищает данные таблицы: убирает переносы строк, None, выравнивает размеры.
	"""
	cleaned_table = []

	if not table:
		return cleaned_table

	# Находим максимальное количество колонок
	max_cols = max(len(row) for row in table) if table else 0

	for row in table:
		cleaned_row = []
		for cell in row:
			# Обрабатываем каждую ячейку
			if cell is None:
				cleaned_cell = ""
			else:
				# Заменяем переносы строк на пробелы и чистим
				cleaned_cell = str(cell).replace('\n', ' ').replace('\r', ' ')
				# Убираем лишние пробелы
				cleaned_cell = re.sub(r'\s+', ' ', cleaned_cell).strip()

			cleaned_row.append(cleaned_cell)

		# Добиваем строку до максимального количества колонок
		while len(cleaned_row) < max_cols:
			cleaned_row.append("")

		cleaned_table.append(cleaned_row)

	return cleaned_table


def print_formatted_table(table: list[list[Any]], title: str = "ТАБЛИЦА", max_col_width: int = 30):
	"""
	Отображает таблицу с ограничением ширины КАЖДОЙ колонки.
	Если ячейка превышает max_col_width - укорачивает с '...'
	"""
	if not table:
		print("   [пустая таблица]")
		return

	cleaned_table = clean_table_data(table)
	if not cleaned_table:
		return

	max_cols = len(cleaned_table[0])

	# 1. Определяем естественные ширины колонок (но не больше max_col_width)
	col_widths = [0] * max_cols
	for row in cleaned_table:
		for i, cell in enumerate(row):
			if i < max_cols:
				# Естественная ширина, но не больше ограничения
				cell_width = min(len(cell), max_col_width)
				col_widths[i] = max(col_widths[i], cell_width)

	# 2. Рассчитываем общую ширину таблицы
	total_width = sum(col_widths) + (max_cols - 1) * 3  # " │ " между колонками

	# 3. Отрисовываем таблицу
	print(f"   ┌{'─' * total_width}┐")
	print(f"   │ {title.center(total_width - 2)} │")
	print(f"   ├{'─' * total_width}┤")

	for row in cleaned_table:
		cells = []
		for i, cell in enumerate(row):
			if i < len(col_widths):
				display_cell = cell
				# Укорачиваем если превышает лимит
				if len(display_cell) > col_widths[i]:
					display_cell = display_cell[:col_widths[i] - 3] + "..."
				cells.append(display_cell.ljust(col_widths[i]))
			else:
				cells.append("")
		print(f"   {' │ '.join(cells)}")

	print(f"   └{'─' * total_width}┘")
