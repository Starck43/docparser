import sys
from pathlib import Path
from openpyxl import Workbook
from sqlmodel import Session, select

from models import Document


def export_to_console(session: Session):
	"""Вывести содержимое таблицы документов в консоль"""
	docs = session.exec(select(Document)).all()

	for doc in docs:
		print(f"[{doc.id}] {doc.filename}\n{doc.content_text}\n{'-' * 40}")


def export_to_xls(session: Session, output_file: Path):
	"""Экспортировать документы в XLS"""
	docs = session.exec(select(Document)).all()

	wb = Workbook()
	ws = wb.active
	ws.title = "Documents"
	ws.append(["ID", "Filename", "Content"])

	for doc in docs:
		ws.append([doc.id, doc.filename, doc.content_text])

	wb.save(output_file)
	print(f"Данные экспортированы в {output_file}")
