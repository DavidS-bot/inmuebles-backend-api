# app/config.py
import os

class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/dev.db")
    app_data_dir: str = os.getenv("APP_DATA_DIR", "./data")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24  # 1 día

settings = Settings()


