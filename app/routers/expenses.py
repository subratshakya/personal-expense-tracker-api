import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.category import Category
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseListResponse
from app.services.currency_service import convert_to_base
from app.services.s3_service import upload_file, generate_presigned_url, delete_file

router = APIRouter(prefix="/expenses", tags=["Expenses"])


def _expense_to_response(expense: Expense, category_name: str) -> ExpenseResponse:
    """Convert an Expense ORM model to an ExpenseResponse schema."""
    bill_url = None
    if expense.bill_image_key:
        bill_url = generate_presigned_url(expense.bill_image_key)

    return ExpenseResponse(
        id=expense.id,
        category_id=expense.category_id,
        category_name=category_name,
        amount=expense.amount,
        currency=expense.currency,
        base_amount=expense.base_amount,
        description=expense.description,
        expense_date=expense.expense_date,
        bill_image_url=bill_url,
        created_at=expense.created_at,
        updated_at=expense.updated_at,
    )


async def _get_user_category(db: AsyncSession, category_id: uuid.UUID, user_id: uuid.UUID) -> Category:
    """Fetch a category belonging to the user, or raise 404."""
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return category


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    data: ExpenseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new expense linked to a category."""
    category = await _get_user_category(db, data.category_id, user.id)

    base_amount = convert_to_base(data.amount, data.currency, user.base_currency)

    expense = Expense(
        user_id=user.id,
        category_id=data.category_id,
        amount=data.amount,
        currency=data.currency,
        base_amount=base_amount,
        description=data.description,
        expense_date=data.expense_date,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)

    return _expense_to_response(expense, category.name)


@router.get("/", response_model=ExpenseListResponse)
async def list_expenses(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    start_date: Optional[date] = Query(None, description="Filter by start date (inclusive)"),
    end_date: Optional[date] = Query(None, description="Filter by end date (inclusive)"),
    category_id: Optional[uuid.UUID] = Query(None, description="Filter by category ID"),
    limit: int = Query(20, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """
    List expenses with optional filtering by date range and category,
    plus pagination (limit/offset).
    """
    query = select(Expense).where(Expense.user_id == user.id)
    count_query = select(func.count(Expense.id)).where(Expense.user_id == user.id)

    # Apply filters
    if start_date:
        query = query.where(Expense.expense_date >= start_date)
        count_query = count_query.where(Expense.expense_date >= start_date)
    if end_date:
        query = query.where(Expense.expense_date <= end_date)
        count_query = count_query.where(Expense.expense_date <= end_date)
    if category_id:
        query = query.where(Expense.category_id == category_id)
        count_query = count_query.where(Expense.category_id == category_id)

    # Total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Fetch page
    query = query.order_by(Expense.expense_date.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    expenses = result.scalars().all()

    # Fetch category names
    cat_ids = {e.category_id for e in expenses}
    if cat_ids:
        cat_result = await db.execute(select(Category).where(Category.id.in_(cat_ids)))
        cat_map = {c.id: c.name for c in cat_result.scalars().all()}
    else:
        cat_map = {}

    return ExpenseListResponse(
        expenses=[
            _expense_to_response(e, cat_map.get(e.category_id, "Unknown"))
            for e in expenses
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single expense by ID, including a signed URL for the bill image if present."""
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")

    cat_result = await db.execute(select(Category).where(Category.id == expense.category_id))
    category = cat_result.scalar_one_or_none()

    return _expense_to_response(expense, category.name if category else "Unknown")


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing expense. Only provided fields are updated."""
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")

    if data.category_id is not None:
        await _get_user_category(db, data.category_id, user.id)
        expense.category_id = data.category_id

    if data.description is not None:
        expense.description = data.description
    if data.expense_date is not None:
        expense.expense_date = data.expense_date

    # Recalculate base_amount if amount or currency changed
    if data.amount is not None or data.currency is not None:
        expense.amount = data.amount if data.amount is not None else expense.amount
        expense.currency = data.currency if data.currency is not None else expense.currency
        expense.base_amount = convert_to_base(expense.amount, expense.currency, user.base_currency)

    await db.commit()
    await db.refresh(expense)

    cat_result = await db.execute(select(Category).where(Category.id == expense.category_id))
    category = cat_result.scalar_one_or_none()

    return _expense_to_response(expense, category.name if category else "Unknown")


@router.delete("/{expense_id}", status_code=status.HTTP_200_OK)
async def delete_expense(
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an expense and its associated bill image from storage."""
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")

    # Delete bill image from S3 if it exists
    if expense.bill_image_key:
        try:
            delete_file(expense.bill_image_key)
        except Exception:
            pass  # Log but don't fail the delete

    await db.delete(expense)
    await db.commit()
    return {"detail": "Expense deleted successfully."}


@router.post("/{expense_id}/upload-bill", response_model=ExpenseResponse)
async def upload_bill(
    expense_id: uuid.UUID,
    file: UploadFile = File(..., description="Bill/receipt image (JPEG, PNG, etc.)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a bill/receipt image for a specific expense."""
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file.content_type}'. Allowed: {', '.join(allowed_types)}",
        )

    # Max 10MB
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit.",
        )

    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")

    # Delete old bill image if exists
    if expense.bill_image_key:
        try:
            delete_file(expense.bill_image_key)
        except Exception:
            pass

    # Upload new image
    object_key = upload_file(content, file.filename or "bill.jpg", str(user.id))
    expense.bill_image_key = object_key

    await db.commit()
    await db.refresh(expense)

    cat_result = await db.execute(select(Category).where(Category.id == expense.category_id))
    category = cat_result.scalar_one_or_none()

    return _expense_to_response(expense, category.name if category else "Unknown")
