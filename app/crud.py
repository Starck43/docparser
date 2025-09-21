import json
from typing import Optional, Sequence, Callable, List, Tuple, Dict

from sqlalchemy import Select, ColumnElement
from sqlmodel import Session, select, delete

from . import models
from .models import Document, ProductPlan, DocumentCreate


def create_document(db: Session, document_data: 'DocumentCreate') -> Document:
	"""Создает документ с планами."""

	db_document = Document(
		file_path=document_data.file_path,
		agreement_number=document_data.agreement_number,
		customer_names=json.dumps(document_data.customer_names) if document_data.customer_names else None,
		year=document_data.year,
		allowed_deviation=document_data.allowed_deviation,
		validation_errors=json.dumps(document_data.validation_errors) if document_data.validation_errors else None
	)

	db.add(db_document)
	db.commit()
	db.refresh(db_document)

	# Сохраняем планы
	for plan_data in document_data.plans:
		db_plan = ProductPlan(
			**plan_data.model_dump(),
			document_id=db_document.id
		)
		db.add(db_plan)

	db.commit()
	db.refresh(db_document)
	return db_document


def get_document_by_file_path(db: Session, file_path: str) -> Optional[models.Document]:
	"""
	Находит документ по пути к файлу.
	"""
	query: Select = select(models.Document).where(models.Document.file_path == file_path)
	return db.exec(query).first()


def get_documents(
		db: Session,
		year: Optional[int] = None,
		skip: int = 0,
		limit: Optional[int] = None
) -> Sequence[Document]:
	"""
	Получает документы с предзагруженными планами.
	"""
	query = select(Document)

	if year is not None:
		query = query.where(Document.year == year)

	query = query.offset(skip)

	if limit is not None:
		query = query.limit(limit)

	documents = db.exec(query).all()

	# Загружаем планы для каждого документа
	for document in documents:
		db.refresh(document)

	return documents


def get_documents_with_plans(
		db: Session,
		year: Optional[int] = None,
		skip: int = 0,
		limit: Optional[int] = None
) -> list[tuple[Document, dict[str | None, list[None]]]]:
	"""
	Получает документы с группированными планами по покупателям.
	Возвращает список кортежей (документ, {покупатель: [месячные_планы]})
	"""
	query = select(Document)

	if year is not None:
		query = query.where(Document.year == year)

	query = query.offset(skip)

	if limit is not None:
		query = query.limit(limit)

	documents = db.exec(query).all()

	results = []
	for document in documents:
		db.refresh(document)  # Загружаем связанные планы

		# Группируем планы по покупателям и месяцам
		customer_plans = {}
		for plan in document.plans:
			customer_key = plan.customer_name or "Все покупатели"
			if customer_key not in customer_plans:
				customer_plans[customer_key] = [None] * 12

			if 1 <= plan.month <= 12 and plan.planned_quantity is not None:
				month_index = plan.month - 1
				# инициализируем и суммируем
				if customer_plans[customer_key][month_index] is None:
					customer_plans[customer_key][month_index] = plan.planned_quantity
				else:
					customer_plans[customer_key][month_index] += plan.planned_quantity

		results.append((document, customer_plans))

	return results


def get_documents_by_year_range(
		db: Session,
		start_year: int,
		end_year: int,
		limit: Optional[int] = None
) -> Sequence[models.Document]:
	"""
	Получает документы за диапазон лет.
	"""
	query: Select = select(models.Document).where(
		models.Document.year >= start_year,
		models.Document.year <= end_year
	)

	if limit is not None:
		query = query.limit(limit)

	return db.exec(query).all()


def get_documents_with_errors(
		db: Session,
		year: Optional[ColumnElement[int]] = None,
		limit: Optional[int] = None
) -> Sequence[models.Document]:
	"""
	Получает документы с ошибками валидации.
	"""
	query: Select = select(models.Document).where(
		models.Document.validation_errors is not None
	)

	# Добавляем фильтр по году если указан
	if year is not None:
		query = query.where(models.Document.year == year)

	if limit is not None:
		query = query.limit(limit)

	documents: Sequence[models.Document] = db.exec(query).all()

	# Загружаем связанные с документом планы
	for document in documents:
		db.refresh(document)

	return documents


def delete_documents_by_year(db: Session, year: Optional[int] = None) -> int | Callable[[], int]:
	"""
	Удаляет документы за указанный год (или все если год не указан).
	Сначала удаляет связанные записи ProductPlan, затем сами документы.
	Возвращает количество удаленных документов.
	"""
	# Сначала находим все документы, которые нужно удалить
	if year is not None:
		query = select(models.Document).where(models.Document.year == year)
	else:
		query = select(models.Document)

	documents_to_delete = db.exec(query).all()

	if not documents_to_delete:
		return 0  # Нет документов для удаления

	# Получаем ID документов для удаления
	document_ids = [doc.id for doc in documents_to_delete]

	# Удаляем связанные записи ProductPlan
	db.exec(
		delete(models.ProductPlan)
		.where(models.ProductPlan.document_id.in_(document_ids))
	)

	# Удаляем сами документы
	deleted_count = db.exec(
		delete(models.Document)
		.where(models.Document.id.in_(document_ids))
	).rowcount

	db.commit()
	return deleted_count


def delete_all_documents(db: Session) -> int:
	"""
	Удаляет все документы и связанные планы из БД.
	Возвращает количество удаленных документов.
	"""
	deleted_count = db.exec(select(models.Document)).all()
	for document in deleted_count:
		db.delete(document)
	db.commit()
	return len(deleted_count)
