"""Pydantic models for check configuration and results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


class CheckResult(BaseModel):
    check_name: str
    table: str
    column: str | None = None
    status: CheckStatus
    message: str
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SchemaExpectation(BaseModel):
    column: str
    dtype: str
    nullable: bool = True


class CheckConfig(BaseModel):
    check_name: str
    table: str
    column: str | None = None
    params: dict[str, float | int | str | bool | list[str]] = Field(
        default_factory=dict
    )
