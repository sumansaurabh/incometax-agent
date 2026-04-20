from dataclasses import dataclass


@dataclass
class DatabaseSession:
    dsn: str = "postgresql://localhost:5432/itx"


def get_session() -> DatabaseSession:
    return DatabaseSession()
