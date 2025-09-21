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
	customer_names: Optional[str] = None  # строка со списком покупателей
	allowed_deviation: Optional[str] = None
	validation_errors: Optional[str] = None
	created_at: datetime = Field(default_factory=datetime.now)

	plans: list["ProductPlan"] = Relationship(back_populates="document")

	def get_plans_summary(self) -> dict[str, list[Optional[float]]]:
		"""
		Возвращает сводку планов в виде {customer_name: [янв, фев, ..., дек]}
		"""
		summary = {}

		# Сортируем планы по году и месяцу
		sorted_plans = sorted(self.plans, key=lambda x: (x.year, x.month))

		for plan in sorted_plans:
			customer_key = plan.customer_name or "all"

			if customer_key not in summary:
				summary[customer_key] = [None] * 12

			if 1 <= plan.month <= 12 and plan.planned_quantity is not None:
				summary[customer_key][plan.month - 1] = plan.planned_quantity

		return summary


class ProductPlan(SQLModel, table=True):
	id: Optional[int] = Field(default=None, primary_key=True)
	month: int
	year: int
	planned_quantity: Optional[float]
	customer_name: Optional[str]  # Конкретный покупатель для этого плана

	document_id: int = Field(foreign_key="document.id")
	document: Document = Relationship(back_populates="plans")

	# Сортируем по году и месяцу
	class Config:
		arbitrary_types_allowed = True


# Pydantic модели
class DocumentCreate(BaseModel):
	file_path: str
	agreement_number: Optional[str] = None
	year: int = get_current_year()
	customer_names: list[str] = []
	allowed_deviation: Optional[str] = None  # Допустимое отклонение от плана
	validation_errors: list[str] = []
	plans: list['ProductPlanCreate'] = []

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
	month: int
	year: int
	planned_quantity: Optional[float] = None
	customer_name: Optional[str] = None

