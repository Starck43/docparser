import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator
from sqlmodel import SQLModel, Field, Relationship


# Таблицы БД
class Document(SQLModel, table=True):
	id: Optional[int] = Field(default=None, primary_key=True)
	file_path: str
	agreement_number: Optional[str] = Field(index=True)  # № соглашения (5Ф)
	customer_name: Optional[str]  # ООО «ААА» и ООО «БББ»
	validation_errors: Optional[str] = None  # JSON-строка для списка ошибок
	created_at: datetime = Field(default_factory=datetime.now)

	# Связь "один ко многим" с планами поставок
	product_plans: list["ProductPlan"] = Relationship(back_populates="document")


class ProductPlan(SQLModel, table=True):
	id: Optional[int] = Field(default=None, primary_key=True)
	month: int  # Месяц поставки (1-12)
	year: int  # Год поставки (2025)
	planned_quantity: Optional[float]  # Плановое количество (тонны)

	document_id: int = Field(foreign_key="document.id")
	# Связь "многие к одному" с соглашением
	document: Document = Relationship(back_populates="product_plans")


# Модели для данных (не для БД)
class ProductPlanCreate(BaseModel):
	product_name: str
	month: int
	year: int
	planned_quantity: Optional[float] = None


class DocumentCreate(BaseModel):
	file_path: str
	agreement_number: Optional[str] = None
	customer_name: Optional[str] = None
	validation_errors: list[str] = []  # Список ошибок
	product_plans: list[ProductPlanCreate] = []

	# Валидатор для номера соглашения
	@field_validator('agreement_number')
	def clean_agreement_number(self, v):
		if v and isinstance(v, str):
			# Убираем лишние пробелы, кавычки и т.д.
			return re.sub(r'[\s«»"]', '', v)
		return v
