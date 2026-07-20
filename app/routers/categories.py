from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new expense category for the authenticated user."""
    # Check for duplicate category name for this user
    result = await db.execute(
        select(Category).where(Category.user_id == user.id, Category.name == data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{data.name}' already exists.",
        )

    category = Category(user_id=user.id, name=data.name)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all categories for the authenticated user."""
    result = await db.execute(
        select(Category).where(Category.user_id == user.id).order_by(Category.name)
    )
    return result.scalars().all()


@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(
    category_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a category. Also deletes all associated expenses."""
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user.id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found.",
        )

    await db.delete(category)
    await db.commit()
    return {"detail": f"Category '{category.name}' deleted successfully."}
