import re
from typing import Any


def print_formatted_table(table: list[list[str]], title: str = "ТАБЛИЦА", max_col_width: int = 15):
	"""
	Отображает таблицу: первая колонка 25, остальные до max_col_width.
	"""
	if not table:
		print("   [пустая таблица]")
		return

	max_cols = max(len(row) for row in table) if table else 0

	# Первая колонка 25, остальные max_col_width
	col_widths = [25]  # Первая колонка фиксированная
	for i in range(1, max_cols):
		col_widths.append(max_col_width)

	# Принудительно обрезаем данные до нужной ширины
	cleaned_table = []
	for row in table:
		cleaned_row = []
		for i, cell in enumerate(row):
			if i < len(col_widths):
				cell_str = str(cell).replace('\n', ' ').strip()
				if len(cell_str) > col_widths[i]:
					cell_str = cell_str[:col_widths[i] - 3] + "..."
				cleaned_row.append(cell_str)
			else:
				cleaned_row.append("")
		while len(cleaned_row) < max_cols:
			cleaned_row.append("")
		cleaned_table.append(cleaned_row)

	# Рассчитываем общую ширину
	total_width = sum(col_widths) + (max_cols - 1) * 3

	# Ограничиваем заголовок
	if len(title) > total_width - 4:
		title = title[:total_width - 7] + "..."

	# Отрисовываем таблицу
	print(f"   ┌{'─' * total_width}┐")
	print(f"   │ {title.center(total_width - 2)} │")
	print(f"   ├{'─' * total_width}┤")

	for row in cleaned_table:
		cells = []
		for i, cell in enumerate(row):
			if i < len(col_widths):
				cells.append(cell.ljust(col_widths[i]))
			else:
				cells.append("".ljust(max_col_width))
		print(f"     {' │ '.join(cells)}")

	print(f"   └{'─' * total_width}┘")
