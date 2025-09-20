from typing import Optional

from sqlalchemy import Select
from sqlmodel import Session, select
from . import models


def create_document(db: Session, document_data: models.DocumentCreate) -> models.Document:
	"""
	Создает новый документ и связанные планы поставок в базе данных.
	"""
	# Конвертируем Pydantic-модель в SQLModel-модель
	db_document = models.Document(
		file_path=document_data.file_path,
		agreement_number=document_data.agreement_number,
		customer_name=document_data.customer_name,
		validation_errors=str(document_data.validation_errors) if document_data.validation_errors else None
	)

	db.add(db_document)
	db.commit()
	db.refresh(db_document)

	# Создаем планы поставок
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
	statement: Select = select(models.Document).where(models.Document.file_path == file_path)
	return db.exec(statement).first()


def get_documents_with_plans(db: Session, skip: int = 0, limit: int = 100):
	"""
	Получает документы с их планами поставок.
	"""
	return db.exec(
		select(models.Document)
		.offset(skip)
		.limit(limit)
	).all()
