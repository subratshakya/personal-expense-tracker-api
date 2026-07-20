from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CategorySummary(BaseModel):
    category_name: str
    total_spent: Decimal
    budget_limit: Optional[Decimal] = None
    is_over_budget: bool = False


class MonthlySummary(BaseModel):
    year: int
    month: int
    total_spent: Decimal
    categories: list[CategorySummary]
