"""Harness model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jefe.data.models.base import BaseModel

if TYPE_CHECKING:
    from jefe.data.models.harness_config import HarnessConfig


class Harness(BaseModel):
    """Registered harness adapter."""

    __tablename__ = "harnesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    configs: Mapped[list[HarnessConfig]] = relationship(
        back_populates="harness",
        cascade="all, delete-orphan",
        order_by="HarnessConfig.id",
    )
