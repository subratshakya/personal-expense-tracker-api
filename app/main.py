import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.s3_service import ensure_bucket_exists

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup: ensure the S3 bucket exists
    logger.info("Starting up — ensuring S3 bucket exists...")
    try:
        ensure_bucket_exists()
    except Exception as e:
        logger.warning(f"Could not connect to S3/MinIO on startup: {e}")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="Personal Expense Tracker API",
    description=(
        "A RESTful API for tracking daily expenses, managing categories, "
        "uploading bill receipts, and viewing financial summaries."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.routers import auth, categories, expenses, budgets, summary, export

app.include_router(auth.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(expenses.router, prefix="/api/v1")
app.include_router(budgets.router, prefix="/api/v1")
app.include_router(summary.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")


from fastapi.responses import RedirectResponse

@app.get("/", tags=["Root"])
async def root():
    """Redirect root to interactive API documentation."""
    return RedirectResponse(url="/docs")
