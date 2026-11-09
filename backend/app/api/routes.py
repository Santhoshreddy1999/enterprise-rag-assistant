from __future__ import annotations

import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, File, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.dependencies import (
    AnswerProviderDep,
    CurrentUser,
    EmbeddingDep,
    RetrieverDep,
    SessionDep,
    SettingsDep,
)
from app.api.schemas import (
    AuthCredentials,
    CitationOut,
    ConversationCreate,
    ConversationOut,
    DocumentOut,
    EvaluationCaseOut,
    HealthOut,
    MessageCreate,
    MessageOut,
    RetrievalEvaluationCreate,
    RetrievalEvaluationOut,
    UserOut,
)
from app.application.services import (
    EvaluationCaseInput,
    authenticate_user,
    create_conversation,
    delete_document,
    ingest_document,
    list_conversations,
    list_documents,
    list_messages,
    register_user,
    run_retrieval_evaluation,
    send_message,
)
from app.core.security import create_access_token
from app.core.telemetry import metrics_response
from app.infrastructure.database import Database
from app.infrastructure.documents import (
    DocumentTooLargeError,
    validate_document_metadata,
)
from app.infrastructure.models import Message, User

router = APIRouter()


def _set_access_cookie(response: Response, user: User, settings: SettingsDep) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=create_access_token(user.id, settings),
        max_age=settings.jwt_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1",
    )


@router.post(
    "/auth/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: AuthCredentials,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    user = register_user(
        session,
        email=str(payload.email),
        password=payload.password,
    )
    _set_access_cookie(response, user, settings)
    return user


@router.post("/auth/login", response_model=UserOut)
def login(
    payload: AuthCredentials,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    user = authenticate_user(
        session,
        email=str(payload.email),
        password=payload.password,
    )
    _set_access_cookie(response, user, settings)
    return user


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def logout(settings: SettingsDep) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/api/v1",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


def _read_upload(file: UploadFile, limit: int) -> bytes:
    content = bytearray()
    try:
        while block := file.file.read(1024 * 1024):
            content.extend(block)
            if len(content) > limit:
                raise DocumentTooLargeError("upload exceeds the 10 MiB limit")
    finally:
        file.file.close()
    return bytes(content)


@router.post(
    "/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUser,
    embedding: EmbeddingDep,
    file: Annotated[UploadFile, File()],
) -> object:
    metadata = validate_document_metadata(file.filename, file.content_type)
    content = _read_upload(file, settings.upload_max_bytes)
    return ingest_document(
        session,
        user_id=user.id,
        metadata=metadata,
        content=content,
        settings=settings,
        embedding=embedding,
    )


@router.get("/documents", response_model=list[DocumentOut])
def documents(session: SessionDep, user: CurrentUser) -> list[object]:
    return cast(list[object], list_documents(session, user_id=user.id))


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def remove_document(
    document_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    delete_document(
        session,
        user_id=user.id,
        document_id=document_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
def new_conversation(
    payload: ConversationCreate,
    session: SessionDep,
    user: CurrentUser,
) -> object:
    return create_conversation(
        session,
        user_id=user.id,
        title=payload.title,
    )


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(session: SessionDep, user: CurrentUser) -> list[object]:
    return cast(list[object], list_conversations(session, user_id=user.id))


def _message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=cast(Literal["user", "assistant"], message.role),
        content=message.content,
        created_at=message.created_at,
        citations=[
            CitationOut(
                index=citation.citation_index,
                document_id=citation.document_id,
                filename=citation.filename,
                chunk_id=citation.chunk_id,
                page=citation.page,
                excerpt=citation.excerpt,
            )
            for citation in message.citations
        ],
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
def conversation_messages(
    conversation_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[MessageOut]:
    return [
        _message_out(message)
        for message in list_messages(
            session,
            user_id=user.id,
            conversation_id=conversation_id,
        )
    ]


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    session: SessionDep,
    user: CurrentUser,
    retriever: RetrieverDep,
    provider: AnswerProviderDep,
) -> MessageOut:
    message = send_message(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        content=payload.content,
        top_k=payload.top_k,
        retriever=retriever,
        provider=provider,
    )
    return _message_out(message)


@router.post(
    "/evaluations/retrieval",
    response_model=RetrievalEvaluationOut,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_retrieval(
    payload: RetrievalEvaluationCreate,
    session: SessionDep,
    user: CurrentUser,
    retriever: RetrieverDep,
) -> RetrievalEvaluationOut:
    result = run_retrieval_evaluation(
        session,
        user_id=user.id,
        name=payload.name,
        top_k=payload.top_k,
        cases=[
            EvaluationCaseInput(
                query=case.query,
                expected_document_ids=case.expected_document_ids,
            )
            for case in payload.cases
        ],
        retriever=retriever,
    )
    return RetrievalEvaluationOut(
        id=result.run.id,
        name=result.run.name,
        top_k=result.run.top_k,
        hit_rate=result.hit_rate,
        mean_reciprocal_rank=result.mean_reciprocal_rank,
        cases=[
            EvaluationCaseOut(
                query=case.query,
                expected_document_ids=case.expected_document_ids,
                retrieved_document_ids=case.retrieved_document_ids,
                hit=case.hit,
                reciprocal_rank=case.reciprocal_rank,
            )
            for case in result.cases
        ],
        created_at=result.run.created_at,
    )


@router.get("/health/live", response_model=HealthOut)
def live() -> HealthOut:
    return HealthOut(status="ok")


@router.get(
    "/health/ready",
    response_model=HealthOut,
    responses={503: {"model": HealthOut}},
)
def ready(request: Request) -> HealthOut | JSONResponse:
    database = cast(Database, request.app.state.database)
    if not database.is_ready():
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return HealthOut(status="ok")


@router.get("/metrics", response_class=Response)
def metrics() -> Response:
    return metrics_response()
