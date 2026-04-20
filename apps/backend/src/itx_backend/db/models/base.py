from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass
class BaseRecord:
    id: str = ""
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid4())
