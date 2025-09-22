from datetime import datetime
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.hyperlink import Hyperlink

from app.config import settings
from app.models import Document, DocumentCreate
from app.utils.base import get_unique_filename, format_string_list


def export_to_xls_with_months(
		documents: list[Document | DocumentCreate],
		year: int,
		export_dir: Optional[Path] = None,
		postfix: str = "",
		force_overwrite: bool = False
) -> Path:
	"""
	Экспортирует список документов в XLS файл с детализацией по месяцам.
	Использует логику как в step5_view_documents.
	"""

	export_directory = export_dir or settings.EXPORT_DIR

	# Создаем рабочую книгу и лист
	wb = Workbook()
	ws = wb.active
	ws.title = f"{year}"

	# Убираем сетку листа
	ws.sheet_view.showGridLines = False

	# Добавляем заголовок
	ws['A1'] = f"Сводные данные плановых закупок по контрагентам за {year} год"
	ws['A1'].font = Font(bold=True, size=18)

	# Добавляем дату создания
	creation_date = datetime.now().strftime("%d.%m.%Y %H:%M")
	ws['A2'] = f"Дата формирования: {creation_date}"
	ws['A2'].font = Font(italic=True)

	# Создаем шапку таблицы (начинаем с 4 строки)
	headers = [
		"Файл",
		"Контрагенты",
		"№ согл.",
		"Год",
		*[f"{i:02d}" for i in range(1, 13)],  # Генерация месяцев 01-12
		"Итого",
		"+/-",
		"Ошибки"
	]

	# Записываем заголовки в четвертую строку
	for col_num, header in enumerate(headers, 1):
		col_letter = get_column_letter(col_num)
		cell = ws[f"{col_letter}4"]
		cell.value = header
		cell.font = Font(bold=True)
		cell.alignment = Alignment(vertical='center')

		# Выравнивание для разных колонок
		if col_num == 1:  # Файл
			cell.alignment = Alignment(horizontal='left')
		elif col_num in [2, 3]:  # Контрагенты, № соглашения
			cell.alignment = Alignment(horizontal='left')
		elif col_num == 4:  # Год
			cell.alignment = Alignment(horizontal='left')
		elif 5 <= col_num <= 16:  # Месяцы 01-12
			cell.alignment = Alignment(horizontal='center')
		elif col_num == 17:  # Итого
			cell.alignment = Alignment(horizontal='right')
		elif col_num == 18:  # +/-
			cell.alignment = Alignment(horizontal='center')
		elif col_num == 19:  # Ошибки
			cell.alignment = Alignment(horizontal='left')

	# Заполняем данные (начинаем с 5 строки)
	row_num = 5

	for doc in documents:
		# Пропускаем документы без данных
		if not hasattr(doc, 'plans') or not doc.plans:
			continue

		# Получаем имя файла безопасным способом
		file_path_obj = Path(doc.file_path) if isinstance(doc.file_path, str) else doc.file_path
		file_name = file_path_obj.name

		customer_names = format_string_list(doc.customer_names, default_text="не определен")

		base_data = {
			"file_path": str(doc.file_path),
			"customer_names": customer_names,
			"agreement_number": doc.agreement_number,
			"year": doc.year,
			"allowed_deviation": doc.allowed_deviation,
			"validation_errors": format_string_list(doc.validation_errors)
		}

		# Суммируем планы по месяцам (как в step5_view_documents)
		monthly_totals = [0.0] * 12
		for plan in doc.plans:
			if 1 <= plan.month <= 12 and plan.planned_quantity is not None:
				month_index = plan.month - 1
				monthly_totals[month_index] += plan.planned_quantity

		# Добавляем значок файла и гиперссылку (колонка A)
		cell = ws[f'A{row_num}']
		cell.value = "📄"
		cell.hyperlink = Hyperlink(
			display=f"Источник {file_name}",
			ref=f"A{row_num}",
			target=str(doc.file_path),
			tooltip=f"Открыть файл: {file_name}"
		)
		cell.font = Font(color="0000FF", underline='single')
		cell.alignment = Alignment(horizontal='left', vertical='center')

		# Данные документа
		ws[f'B{row_num}'] = base_data["customer_names"]  # Контрагенты из документа
		ws[f'B{row_num}'].alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)

		ws[f'C{row_num}'] = base_data["agreement_number"]
		ws[f'C{row_num}'].alignment = Alignment(horizontal='left')

		ws[f'D{row_num}'] = base_data["year"]
		ws[f'D{row_num}'].alignment = Alignment(horizontal='left')

		# Данные по месяцам (колонки E-P)
		total_quantity = 0
		for month_idx, month_value in enumerate(monthly_totals):
			month_col = get_column_letter(5 + month_idx)  # Колонки E-P (5-16)
			value = month_value if month_value != 0 else None
			cell = ws[f'{month_col}{row_num}']
			cell.value = value
			cell.alignment = Alignment(horizontal='center')
			total_quantity += month_value

		# Итоговая сумма (колонка Q)
		total_cell = ws[f'Q{row_num}']
		total_cell.value = total_quantity if total_quantity != 0 else None
		total_cell.alignment = Alignment(horizontal='right')
		total_cell.font = Font(bold=True)  # Жирный шрифт для итого

		# Остальные данные (колонки R-S)
		ws[f'R{row_num}'] = base_data["allowed_deviation"]
		ws[f'R{row_num}'].alignment = Alignment(horizontal='center')

		ws[f'S{row_num}'] = base_data["validation_errors"]
		ws[f'S{row_num}'].alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)

		# Добавляем границы для данных
		for col_num in range(1, 20):  # Колонки A-S
			col_letter = get_column_letter(col_num)
			cell = ws[f'{col_letter}{row_num}']
			cell.border = Border(
				left=Side(style='thin'),
				right=Side(style='thin'),
				bottom=Side(style='thin')
			)

		# Если есть ошибки, красим всю строку в красный
		if doc.validation_errors:
			red_font = Font(color="FF0000")
			for col_letter in ['B', 'C', 'D', 'Q', 'R', 'S']:
				ws[f'{col_letter}{row_num}'].font = red_font
			for month_col in range(5, 17):
				ws[f'{get_column_letter(month_col)}{row_num}'].font = red_font

		row_num += 1

	# Автоподбор ширины колонок
	column_widths = {}
	for column in ws.columns:
		max_length = 0
		column_letter = get_column_letter(column[0].column)
		for cell in column:
			try:
				if cell.value and len(str(cell.value)) > max_length:
					max_length = len(str(cell.value))
			except:
				pass
		column_widths[column_letter] = min(max_length + 2, 15)

	# Особые настройки ширины
	column_widths['A'] = 6  # Файл (иконка)
	column_widths['B'] = 45  # Контрагенты
	column_widths['C'] = 10  # № соглашения
	column_widths['D'] = 6  # Год
	column_widths['Q'] = 10  # Итого
	column_widths['R'] = 6  # +/-
	column_widths['S'] = 20  # Ошибки

	for col_letter, width in column_widths.items():
		ws.column_dimensions[col_letter].width = width

	# Добавляем границы для шапки
	for col_num in range(1, 20):
		col_letter = get_column_letter(col_num)
		cell = ws[f'{col_letter}4']
		cell.border = Border(
			left=Side(style='medium'),
			right=Side(style='medium'),
			top=Side(style='medium'),
			bottom=Side(style='medium')
		)

	# Формируем имя с postfix
	timestamp = datetime.now().strftime("%d-%m-%Y")
	base_filename = f"export_{year}_{timestamp}{postfix}"

	# Используем функцию для уникального имени
	export_file_path = get_unique_filename(
		export_directory,
		base_filename,
		postfix,
		".xlsx",
		force_overwrite=settings.REWRITE_FILE_ON_CONFLICT or force_overwrite
	)

	# Сохраняем файл
	wb.save(export_file_path)

	print(f"[INFO] Данные успешно экспортированы в файл: {export_file_path}")
	return export_file_path
