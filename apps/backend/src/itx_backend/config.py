from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "IncomeTax Agent Backend"
    app_version: str = "0.1.0"
    environment: str = "dev"
    websocket_path: str = "/ws"


settings = Settings()
