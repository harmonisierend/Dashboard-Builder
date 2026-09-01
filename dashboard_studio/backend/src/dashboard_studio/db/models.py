"""SQLAlchemy models.

These four tables (Project, TokenPreset, Generation, Backup) are barely
used in M1 -- they exist now, with an initial Alembic migration, so M2-M6
(design presets, generation history/diffing, dashboard backups/rollback)
never have to touch schema plumbing for the first time under milestone
pressure. Large blobs (uploaded design images, generated YAML, dashboard
backups) live as files under /data/uploads and /data/backups; these rows
hold metadata and paths, not the blobs themselves.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    generations: Mapped[list[Generation]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class TokenPreset(Base):
    """A saved, reusable design-token set (M2+)."""

    __tablename__ = "token_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(255))
    token_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Generation(Base):
    """One dashboard-generation run belonging to a project (M3+)."""

    __tablename__ = "generations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    dashboard_yaml: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="generations")


class Backup(Base):
    """Metadata for a pre-overwrite dashboard backup under /data/backups (M6+)."""

    __tablename__ = "backups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    dashboard_url_path: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
