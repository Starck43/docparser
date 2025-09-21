import re
import json

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator

from app.services.utils import get_current_year


# Таблицы БД
class Document(SQLModel, table=True):
	id: Optional[int] = Field(default=None, primary_key=True)
	file_path: str = Field(unique=True)
	agreement_number: Optional[str] = Field(index=True)
	year: int = Field(default_factory=get_current_year)
	customer_names: Optional[str] = None  # JSON строка со списком покупателей
	validation_errors: Optional[str] = None
	created_at: datetime = Field(default_factory=datetime.now)

	product_plans: list["ProductPlan"] = Relationship(back_populates="document")


class ProductPlan(SQLModel, table=True):
	id: Optional[int] = Field(default=None, primary_key=True)
	month: int
	year: int
	planned_quantity: Optional[float]
	allowed_deviation: Optional[str] = None  # Допустимое отклонение от плана
	product_name: str
	customer_name: Optional[str]  # Конкретный покупатель для этого плана

	document_id: int = Field(foreign_key="document.id")
	document: Document = Relationship(back_populates="product_plans")


# Pydantic модели
class DocumentCreate(BaseModel):
	file_path: str
	agreement_number: Optional[str] = None
	year: int = get_current_year()
	customer_names: list[str] = []
	validation_errors: list[str] = []
	product_plans: list['ProductPlanCreate'] = []

	@field_validator('agreement_number')
	def clean_agreement_number(cls, v):
		if v and isinstance(v, str):
			return re.sub(r'[\s«»"]', '', v)
		return v

	@field_validator('customer_names', mode='before')
	def validate_customer_names(cls, v):
		if isinstance(v, str):
			try:
				return json.loads(v)
			except json.JSONDecodeError:
				return [v]
		return v


class ProductPlanCreate(BaseModel):
	product_name: str
	month: int
	year: int
	planned_quantity: Optional[float] = None
	allowed_deviation: Optional[str] = None
	customer_name: Optional[str] = None

