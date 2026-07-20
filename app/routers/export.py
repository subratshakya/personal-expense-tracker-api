import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.category import Category
from app.models.expense import Expense
from app.models.user import User

router = APIRouter(prefix="/export", tags=["Data Export"])


@router.get("/csv")
async def export_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    year: int = Query(None, description="Year (defaults to current)"),
    month: int = Query(None, description="Month (defaults to current)"),
):
    """
    Download all expenses for a given month as a CSV file.
    """
    now = datetime.now(timezone.utc)
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    # Fetch expenses
    result = await db.execute(
        select(Expense)
        .where(
            Expense.user_id == user.id,
            extract("year", Expense.expense_date) == year,
            extract("month", Expense.expense_date) == month,
        )
        .order_by(Expense.expense_date)
    )
    expenses = result.scalars().all()

    # Fetch category names
    cat_ids = {e.category_id for e in expenses}
    if cat_ids:
        cat_result = await db.execute(select(Category).where(Category.id.in_(cat_ids)))
        cat_map = {c.id: c.name for c in cat_result.scalars().all()}
    else:
        cat_map = {}

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Category", "Description", "Amount", "Currency",
        "Base Amount (USD)", "Created At",
    ])
    for expense in expenses:
        writer.writerow([
            expense.expense_date.isoformat(),
            cat_map.get(expense.category_id, "Unknown"),
            expense.description,
            str(expense.amount),
            expense.currency,
            str(expense.base_amount),
            expense.created_at.isoformat(),
        ])

    output.seek(0)
    filename = f"expenses_{year}_{month:02d}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
