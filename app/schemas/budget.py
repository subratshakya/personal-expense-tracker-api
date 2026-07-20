import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    category_id: uuid.UUID
    monthly_limit: Decimal = Field(..., gt=0, decimal_places=2, examples=[500.00])
    year: int = Field(..., ge=2020, le=2100, examples=[2026])
    month: int = Field(..., ge=1, le=12, examples=[7])


class BudgetResponse(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    monthly_limit: Decimal
    year: int
    month: int
    created_at: datetime

    model_config = {"from_attributes": True}
