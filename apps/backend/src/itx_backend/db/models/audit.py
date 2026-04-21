from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .base import BaseRecord


@dataclass
class FilingAuditTrail(BaseRecord):
    ay_id: str = ""
    event: str = ""
    payload: Optional[dict[str, Any]] = None
    rule_version: str = "v1"
    adapter_version: str = "v1"
