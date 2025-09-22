import json
from typing import Optional, Sequence, Callable, Type

from sqlalchemy import Select, ColumnElement, func
from sqlmodel import Session, select, delete

from .models import Document, ProductPlan, DocumentCreate


def save_document(db: Session, document_data: DocumentCreate) -> Type['Document'] | 'Document':
	"""
	Сохраняет или обновляет документ по его file_path.
	Если документ с таким путем уже существует - обновляет его.
	Если нет - создает новый.
	"""
	# Ищем существующий документ
	existing_doc = get_document_by_file_path(db, str(document_data.file_path))

	if existing_doc:
		# Обновляем существующий документ
		return update_document(db, existing_doc.id, document_data)
	else:
		# Создаем новый документ
		return create_document(db, document_data)


def create_document(db: Session, document_data: 'DocumentCreate') -> 'Document':
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


def update_document(
		db: Session,
		document_id: ColumnElement[int] | int,
		document_data: 'DocumentCreate'
) -> Type['Document']:
	"""
	Обновляет документ и его помесячные планы.
	"""
	# Находим документ
	db_document = db.get(Document, document_id)
	if not db_document:
		raise ValueError(f"Документ с ID {document_id} не найден")

	# Обновляем поля документа
	db_document.agreement_number = document_data.agreement_number
	db_document.customer_names = json.dumps(document_data.customer_names) if document_data.customer_names else None
	db_document.year = document_data.year
	db_document.allowed_deviation = document_data.allowed_deviation
	db_document.validation_errors = json.dumps(
		document_data.validation_errors) if document_data.validation_errors else None

	# Удаляем старые планы
	query = delete(ProductPlan).where(ProductPlan.document_id == document_id)
	db.exec(query)

	# Добавляем новые планы
	for plan_data in document_data.plans:
		db_plan = ProductPlan(
			**plan_data.model_dump(),
			document_id=document_id
		)
		db.add(db_plan)

	db.commit()
	db.refresh(db_document)
	return db_document


def get_document_by_file_path(db: Session, file_path: str) -> Optional['Document']:
	"""
	Находит документ по пути к файлу.
	"""
	query: Select = select(Document).where(Document.file_path == file_path)
	return db.exec(query).first()


def get_documents(
		db: Session,
		year: Optional[int] = None,
		skip: int = 0,
		limit: Optional[int] = None
) -> Sequence[Document]:
	"""
	Получает документы со списком помесячных планов.
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


def get_years_in_documents(db:Session):
	return db.exec(select(Document.year).distinct()).scalar().all()


def get_documents_by_year_range(
		db: Session,
		start_year: int,
		end_year: int,
		limit: Optional[int] = None
) -> Sequence['Document']:
	"""
	Получает документы за диапазон лет.
	"""
	query: Select = select(Document).where(
		Document.year >= start_year,
		Document.year <= end_year
	)

	if limit is not None:
		query = query.limit(limit)

	return db.exec(query).all()


def get_documents_count(
		db: Session,
		year: Optional[ColumnElement[int] | int] = None
) -> int:
	"""Возвращает количество документов."""
	query = select(func.count()).select_from(Document)

	if year is not None:
		query = query.where(Document.year == year)

	result = db.scalar(query)
	return result if result is not None else 0


def get_documents_with_errors(
		db: Session,
		year: Optional[ColumnElement[int]] = None,
		limit: Optional[int] = None
) -> Sequence['Document']:
	"""
	Получает документы с ошибками валидации.
	"""
	query: Select = select(Document).where(
		Document.validation_errors != None
	)

	# Добавляем фильтр по году если указан
	if year is not None:
		query = query.where(Document.year == year)

	if limit is not None:
		query = query.limit(limit)

	documents: Sequence[Document] = db.exec(query).all()

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
		query = select(Document).where(Document.year == year)
	else:
		query = select(Document)

	documents_to_delete = db.exec(query).all()

	if not documents_to_delete:
		return 0  # Нет документов для удаления

	# Получаем ID документов для удаления
	document_ids = [doc.id for doc in documents_to_delete]

	# Удаляем связанные записи ProductPlan
	db.exec(
		delete(ProductPlan)
		.where(ProductPlan.document_id.in_(document_ids))
	)

	# Удаляем сами документы
	deleted_count = db.exec(
		delete(Document)
		.where(Document.id.in_(document_ids))
	).rowcount

	db.commit()
	return deleted_count


def delete_all_documents(db: Session) -> Callable[[], int]:
	"""
	Удаляет все документы и связанные планы из БД.
	Возвращает количество удаленных документов.
	"""
	try:
		# Массовое удаление планов (используем execute вместо exec)
		db.exec(delete(ProductPlan))

		# Массовое удаление документов и получение количества
		result = db.exec(delete(Document))
		deleted_count = result.rowcount

		db.commit()
		return deleted_count

	except Exception as e:
		db.rollback()
		print(f"❌ Ошибка удаления документов: {e}")
		raise
