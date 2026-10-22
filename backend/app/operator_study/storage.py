from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class StudyBase(DeclarativeBase):
    pass


class StudyRecord(StudyBase):
    __tablename__ = "operator_study_state"
    kind: Mapped[str] = mapped_column(String(30), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


def record(session: Session, kind: str, key: str, *, lock: bool = False) -> StudyRecord | None:
    query = select(StudyRecord).where(StudyRecord.kind == kind, StudyRecord.key == key)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def insert(session: Session, kind: str, key: str, value: dict[str, Any]) -> None:
    session.add(StudyRecord(kind=kind, key=key, value=value))
    session.flush()
