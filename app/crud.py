import json
from typing import Optional, Sequence

from sqlalchemy import Select, ColumnElement
from sqlmodel import Session, select

from . import models
from .models import Document


def create_document(db: Session, document_data: models.DocumentCreate) -> models.Document:
	"""Создает документ с планами."""
	db_document = models.Document(
		file_path=document_data.file_path,
		agreement_number=document_data.agreement_number,
		customer_names=json.dumps(document_data.customer_names) if document_data.customer_names else None,
		year=document_data.year,
		validation_errors=json.dumps(document_data.validation_errors) if document_data.validation_errors else None
	)

	db.add(db_document)
	db.commit()
	db.refresh(db_document)

	for plan_data in document_data.product_plans:
		db_plan = models.ProductPlan(
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


def get_documents_with_plans(
		db: Session,
		year: Optional[int] = None,
		skip: int = 0,
		limit: Optional[int] = None
) -> Sequence[Document]:
	"""
	Получает документы с их планами закупок с фильтром по году.
	"""
	# Базовый запрос
	query = select(models.Document)

	# Добавляем фильтр по году если указан
	if year is not None:
		query = query.where(models.Document.year == year)

	# Добавляем пагинацию
	query = query.offset(skip)

	if limit is not None:
		query = query.limit(limit)

	documents = db.exec(query).all()

	# Загружаем связанные планы для каждого документа
	for document in documents:
		db.refresh(document)

	return documents


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


def delete_documents_by_year(db: Session, year: Optional[int] = None) -> int:
	"""
	Удаляет документы за указанный год (или все если год не указан).
	"""
	from sqlmodel import select

	# Явно типизируем query
	if year is not None:
		query = select(models.Document).where(models.Document.year == year)
	else:
		query = select(models.Document)

	documents_to_delete = db.exec(query).all()

	deleted_count = len(documents_to_delete)
	for document in documents_to_delete:
		db.delete(document)

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
