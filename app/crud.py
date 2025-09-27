import json
from typing import Optional, Sequence, Callable, Type, Literal

from sqlalchemy import ColumnElement, func, text, Result
from sqlalchemy.orm import aliased
from sqlalchemy.sql.selectable import Select
from sqlmodel import Session, select, delete, col

from .models import Document, ProductPlan, DocumentCreate


def get_documents_with_plans(
		db: Session,
		use_raw_sql: bool = False,  # Флаг для выбора реализации
		**kwargs
) -> Sequence[tuple[Document, dict[str, list[float | None]]]]:
	"""
	Универсальная функция с выбором реализации.
	"""
	if use_raw_sql:
		return get_documents_with_grouped_plans_sql(db, **kwargs)
	else:
		return get_documents_with_grouped_plans(db, **kwargs)


def get_documents_with_grouped_plans_sql(
		db: Session,
		year: Optional[int] = None,
		skip: int = 0,
		limit: Optional[int] = None
) -> list[tuple[Document, dict[str, list[Optional[float]]]]]:
	"""
		Максимально оптимизированная версия через RAW SQL.
		"""
	# Базовый SQL для документов
	sql = """
		SELECT d.*, p.customer_name, p.month, SUM(p.planned_quantity) as total_quantity
		FROM document d
		LEFT JOIN productplan p ON d.id = p.document_id
		"""

	where_conditions = []
	if year is not None:
		where_conditions.append(f"d.year = {year}")

	if where_conditions:
		sql += " WHERE " + " AND ".join(where_conditions)

	sql += """
		GROUP BY d.id, p.customer_name, p.month
		ORDER BY d.id, p.customer_name, p.month
		"""

	if limit is not None:
		sql += f" LIMIT {limit} OFFSET {skip}"

	result: Result = db.exec(text(sql))
	rows = result.all()

	# Группируем результаты
	documents_map = {}
	for row in rows:
		doc_id = row[0]
		if doc_id not in documents_map:
			# Создаем объект Document из row
			document = Document(
				id=row[0],
				file_path=row[1],
				agreement_number=row[2],
				year=row[3],
				customer_names=row[4],
				allowed_deviation=row[5],
				validation_errors=row[6],
				created_at=row[7]
			)
			documents_map[doc_id] = (document, {})

		document, customer_plans = documents_map[doc_id]
		customer_key = row[8] or "all"  # customer_name
		month = row[9]  # month
		quantity = row[10]  # total_quantity

		if customer_key not in customer_plans:
			customer_plans[customer_key] = [None] * 12

		if 1 <= month <= 12 and quantity is not None:
			customer_plans[customer_key][month - 1] = quantity

	return list(documents_map.values())


def get_documents_with_grouped_plans(
		db: Session,
		year: Optional[ColumnElement[int] | int] = None,
		skip: int = 0,
		limit: Optional[int] = None
) -> Sequence[tuple[Document, dict[str, list[Optional[float]]]]]:
	"""
	Оптимизированное получение документов с группированными планами по покупателям.
	Args:
		db: Сессия базы данных
		year: Фильтр по году (опционально)
		skip: Количество пропускаемых записей
		limit: Ограничение количества записей

	Returns:
		Список кортежей (документ, {покупатель: [планы по месяцам]})
	"""
	subquery = select(Document.id)

	if year is not None:
		subquery = subquery.where(col(Document.year) == year)

	subquery = subquery.offset(skip)

	if limit is not None:
		subquery = subquery.limit(limit)

	subquery = subquery.subquery()
	subquery_alias = aliased(subquery)

	# Основной запрос с агрегацией
	stmt = (
		select(
			Document,
			ProductPlan.customer_name,
			ProductPlan.month,
			func.sum(ProductPlan.planned_quantity).label("total")
		)
		.join(ProductPlan, col(Document.id) == col(ProductPlan.document_id))  # Используем col()
		.where(col(Document.id).in_(select(subquery_alias.c.id)))  # Правильный синтаксис
		.group_by(col(Document.id), col(ProductPlan.customer_name), col(ProductPlan.month))
		.order_by(col(Document.id), col(ProductPlan.customer_name), col(ProductPlan.month))
	)

	rows = db.exec(stmt).all()

	# Группируем результаты по документам
	docs_dict: dict[int, tuple[Document, dict[str, list[Optional[float]]]]] = {}

	for doc, customer, month, total in rows:
		if doc.id not in docs_dict:
			docs_dict[doc.id] = (doc, {})

		_, plans_summary = docs_dict[doc.id]
		customer_key = customer or "all"

		if customer_key not in plans_summary:
			plans_summary[customer_key] = [None] * 12

		if 1 <= month <= 12 and total is not None:
			month_index = month - 1
			plans_summary[customer_key][month_index] = total

	return list(docs_dict.values())


def get_document_with_plans(
		db: Session,
		document_id: int
) -> Document | None:
	"""
	Получает один документ с группированными планами.

	Args:
		db: Сессия базы данных
		document_id: ID документа

	Returns:
		Кортеж (документ, группированные планы) или None если документ не найден
	"""

	from sqlalchemy.orm import selectinload

	query: Select = select(Document).where(Document.id == document_id).options(selectinload(Document.plans))
	document: Optional[Document] = db.exec(query).first()

	if document is None:
		return None

	document.plans = document.get_plans_summary()

	return document


def get_documents(
		db: Session,
		year: Optional[int] = None,
		skip: int = 0,
		limit: Optional[int] = None
) -> Sequence[Document]:
	"""
	Получает документы с планами.
	Args:
		db: Сессия базы данных
		year: Фильтр по году (опционально)
		skip: Количество пропускаемых записей
		limit: Ограничение количества записей

	Returns:
		Список документов
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


def get_document_by_slug(db: Session, slug: str) -> Optional['Document']:
	"""
	Находит документ по пути к файлу.
	"""
	query: Select = select(Document).where(Document.slug == slug)
	return db.exec(query).first()


def get_years_in_documents(db: Session):
	return db.exec(select(Document.year).distinct()).scalar().all()


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
	query: Select = select(Document).where(Document.validation_errors != None)

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


def save_document(
		db: Session,
		document_data: 'DocumentCreate'
) -> tuple[Type['Document'] | 'Document', Literal['created', 'updated']]:
	"""
	Сохраняет или обновляет документ по его file_path.
	Если документ с таким путем уже существует - обновляет его.
	Если нет - создает новый.

	Возвращает:
		кортеж (объект документа и статус: 'created' или 'updated')
	"""

	try:
		# First try to find by slug
		existing_doc = get_document_by_slug(db, document_data.slug)

		if existing_doc:
			return update_document(db, existing_doc.id, document_data), "updated"
		else:
			return create_document(db, document_data), "created"

	except Exception as e:
		db.rollback()  # Rollback в случае ошибки
		raise  # Пробрасываем исключение дальше


def create_document(db: Session, document_data: 'DocumentCreate') -> 'Document':
	"""Создает документ с планами."""

	db_document = Document(
		file_path=document_data.file_path,
		slug=document_data.slug,
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


def bulk_save_documents(db: Session, documents_data: list['DocumentCreate'], update_mode: bool = False) -> int:
	"""
	Массовое сохранение документов с поддержкой режимов обновления.

	Args:
		db: Сессия БД
		documents_data: Список документов для сохранения
		update_mode: False - пропускать существующие, True - обновлять

	Returns:
		Количество сохраненных/обновленных документов
	"""

	saved_count = 0

	for doc_data in documents_data:
		try:
			existing = get_document_by_slug(db, str(doc_data.slug))
			if existing:
				if update_mode:
					update_document(db, existing.id, doc_data)
					saved_count += 1
			else:
				create_document(db, doc_data)
				saved_count += 1
		except Exception as e:
			print(f"❌ Ошибка сохранения документа {doc_data.file_path}: {e}")
			continue

	db.commit()
	return saved_count


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
