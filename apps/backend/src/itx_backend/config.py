import os

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "IncomeTax Agent Backend"
    app_version: str = "0.1.0"
    environment: str = os.getenv("ITX_ENVIRONMENT", "dev")
    websocket_path: str = os.getenv("ITX_WEBSOCKET_PATH", "/ws")
    database_url: str = os.getenv("ITX_DATABASE_URL", "postgresql://itx:itx@localhost:5432/itx")
    database_min_pool_size: int = int(os.getenv("ITX_DATABASE_MIN_POOL_SIZE", "1"))
    database_max_pool_size: int = int(os.getenv("ITX_DATABASE_MAX_POOL_SIZE", "5"))


settings = Settings()
