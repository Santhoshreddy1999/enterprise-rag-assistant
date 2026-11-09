from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AuthCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().casefold()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    media_type: str
    status: str
    chunk_count: int
    created_at: datetime


class ConversationCreate(BaseModel):
    title: ShortText = Field(max_length=200)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime


class MessageCreate(BaseModel):
    content: ShortText = Field(max_length=8_000)
    top_k: int = Field(default=5, ge=1, le=20)


class CitationOut(BaseModel):
    index: int
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    page: int | None
    excerpt: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    citations: list[CitationOut] = Field(default_factory=list)


class EvaluationCaseIn(BaseModel):
    query: ShortText = Field(max_length=4_000)
    expected_document_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)

    @field_validator("expected_document_ids")
    @classmethod
    def unique_document_ids(cls, values: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(values))


class RetrievalEvaluationCreate(BaseModel):
    name: ShortText = Field(max_length=200)
    top_k: int = Field(default=5, ge=1, le=20)
    cases: list[EvaluationCaseIn] = Field(min_length=1, max_length=100)


class EvaluationCaseOut(BaseModel):
    query: str
    expected_document_ids: list[uuid.UUID]
    retrieved_document_ids: list[uuid.UUID]
    hit: bool
    reciprocal_rank: float


class RetrievalEvaluationOut(BaseModel):
    id: uuid.UUID
    name: str
    top_k: int
    hit_rate: float
    mean_reciprocal_rank: float
    cases: list[EvaluationCaseOut]
    created_at: datetime


class HealthOut(BaseModel):
    status: Literal["ok", "not_ready"]
