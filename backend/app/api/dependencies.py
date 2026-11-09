from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.infrastructure.database import Database
from app.infrastructure.embeddings import DeterministicEmbedding
from app.infrastructure.models import User
from app.infrastructure.providers import AnswerProvider
from app.infrastructure.retrieval import HybridRetriever


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_session(request: Request) -> Iterator[Session]:
    database = cast(Database, request.app.state.database)
    with database.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise _unauthorized()
    try:
        user_id = decode_access_token(token, settings)
    except InvalidAccessTokenError as exc:
        raise _unauthorized() from exc
    user = session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise _unauthorized()
    return user


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_embedding(request: Request) -> DeterministicEmbedding:
    return cast(DeterministicEmbedding, request.app.state.embedding)


def get_retriever(request: Request) -> HybridRetriever:
    return cast(HybridRetriever, request.app.state.retriever)


def get_answer_provider(request: Request) -> AnswerProvider:
    return cast(AnswerProvider, request.app.state.answer_provider)


EmbeddingDep = Annotated[DeterministicEmbedding, Depends(get_embedding)]
RetrieverDep = Annotated[HybridRetriever, Depends(get_retriever)]
AnswerProviderDep = Annotated[AnswerProvider, Depends(get_answer_provider)]
