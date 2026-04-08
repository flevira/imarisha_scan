"""Core domain models for document processing jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DocumentJob:
    id: str
    source: str
    status: str
    created_at: datetime
    total_pages: int = 0
