from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://expense_user:expense_pass@db:5432/expense_tracker"

    # JWT
    JWT_SECRET_KEY: str = "super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # S3 / MinIO
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "expense-bills"
    S3_PUBLIC_URL: str = "http://localhost:9000"
    SIGNED_URL_EXPIRY: int = 3600  # seconds

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
