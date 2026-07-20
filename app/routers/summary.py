from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.expense import Expense
from app.models.user import User
from app.schemas.summary import CategorySummary, MonthlySummary

router = APIRouter(prefix="/summary", tags=["Summary"])


@router.get("/monthly", response_model=MonthlySummary)
async def monthly_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    year: int = Query(None, description="Year (defaults to current)"),
    month: int = Query(None, description="Month (defaults to current)"),
):
    """
    Get the total amount spent in a given month, broken down by category.
    Includes budget warning flags when a category exceeds its budget limit.
    """
    now = datetime.now(timezone.utc)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    # Get expenses grouped by category for the given month
    result = await db.execute(
        select(
            Expense.category_id,
            func.sum(Expense.base_amount).label("total_spent"),
        )
        .where(
            Expense.user_id == user.id,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
        .group_by(Expense.category_id)
    )
    category_totals = result.all()

    # Get category names
    cat_ids = [row.category_id for row in category_totals]
    if cat_ids:
        cat_result = await db.execute(select(Category).where(Category.id.in_(cat_ids)))
        cat_map = {c.id: c.name for c in cat_result.scalars().all()}
    else:
        cat_map = {}

    # Get budgets for this month
    budget_result = await db.execute(
        select(Budget).where(
            Budget.user_id == user.id,
            Budget.year == year,
            Budget.month == month,
        )
    )
    budgets = budget_result.scalars().all()
    budget_map = {b.category_id: b.monthly_limit for b in budgets}

    # Build category summaries
    grand_total = Decimal("0.00")
    categories = []
    for row in category_totals:
        total_spent = row.total_spent or Decimal("0.00")
        grand_total += total_spent
        budget_limit = budget_map.get(row.category_id)
        is_over = budget_limit is not None and total_spent > budget_limit

        categories.append(
            CategorySummary(
                category_name=cat_map.get(row.category_id, "Unknown"),
                total_spent=total_spent,
                budget_limit=budget_limit,
                is_over_budget=is_over,
            )
        )

    # Sort by total spent descending
    categories.sort(key=lambda c: c.total_spent, reverse=True)

    return MonthlySummary(
        year=year,
        month=month,
        total_spent=grand_total,
        categories=categories,
    )
