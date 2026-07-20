from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.budget import Budget
from app.models.category import Category
from app.models.user import User
from app.schemas.budget import BudgetCreate, BudgetResponse

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.post("/", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    data: BudgetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set a monthly budget limit for a specific category."""
    # Verify category belongs to user
    cat_result = await db.execute(
        select(Category).where(Category.id == data.category_id, Category.user_id == user.id)
    )
    category = cat_result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

    # Check for existing budget for same (user, category, year, month)
    result = await db.execute(
        select(Budget).where(
            Budget.user_id == user.id,
            Budget.category_id == data.category_id,
            Budget.year == data.year,
            Budget.month == data.month,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Budget for '{category.name}' in {data.year}-{data.month:02d} already exists.",
        )

    budget = Budget(
        user_id=user.id,
        category_id=data.category_id,
        monthly_limit=data.monthly_limit,
        year=data.year,
        month=data.month,
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)

    return BudgetResponse(
        id=budget.id,
        category_id=budget.category_id,
        category_name=category.name,
        monthly_limit=budget.monthly_limit,
        year=budget.year,
        month=budget.month,
        created_at=budget.created_at,
    )


@router.get("/", response_model=list[BudgetResponse])
async def list_budgets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all budgets for the authenticated user."""
    result = await db.execute(
        select(Budget).where(Budget.user_id == user.id).order_by(Budget.year.desc(), Budget.month.desc())
    )
    budgets = result.scalars().all()

    # Fetch category names
    cat_ids = {b.category_id for b in budgets}
    if cat_ids:
        cat_result = await db.execute(select(Category).where(Category.id.in_(cat_ids)))
        cat_map = {c.id: c.name for c in cat_result.scalars().all()}
    else:
        cat_map = {}

    return [
        BudgetResponse(
            id=b.id,
            category_id=b.category_id,
            category_name=cat_map.get(b.category_id, "Unknown"),
            monthly_limit=b.monthly_limit,
            year=b.year,
            month=b.month,
            created_at=b.created_at,
        )
        for b in budgets
    ]


@router.delete("/{budget_id}", status_code=status.HTTP_200_OK)
async def delete_budget(
    budget_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a budget."""
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found.")

    await db.delete(budget)
    await db.commit()
    return {"detail": "Budget deleted successfully."}
