import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, decimal_places=2, examples=[49.99])
    currency: str = Field(default="USD", max_length=3, examples=["USD"])
    description: str = Field(..., min_length=1, max_length=500, examples=["Weekly groceries"])
    expense_date: date = Field(..., examples=["2026-07-20"])


class ExpenseUpdate(BaseModel):
    category_id: Optional[uuid.UUID] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2)
    currency: Optional[str] = Field(default=None, max_length=3)
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    expense_date: Optional[date] = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    amount: Decimal
    currency: str
    base_amount: Decimal
    description: str
    expense_date: date
    bill_image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExpenseListResponse(BaseModel):
    expenses: list[ExpenseResponse]
    total: int
    limit: int
    offset: int
