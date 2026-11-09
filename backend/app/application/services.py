from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.security import (
    consume_dummy_password_check,
    hash_password,
    verify_password,
)
from app.infrastructure.documents import (
    DocumentMetadata,
    chunk_sections,
    parse_document,
)
from app.infrastructure.embeddings import DeterministicEmbedding
from app.infrastructure.models import (
    Chunk,
    Conversation,
    Document,
    EvaluationRun,
    Message,
    MessageCitation,
    User,
)
from app.infrastructure.providers import (
    AnswerProvider,
    LocalExtractiveProvider,
)
from app.infrastructure.retrieval import HybridRetriever


class ConflictError(RuntimeError):
    pass


class InvalidCredentialsError(RuntimeError):
    pass


class ResourceNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvaluationCaseInput:
    query: str
    expected_document_ids: list[uuid.UUID]


@dataclass(frozen=True)
class EvaluationCaseResult:
    query: str
    expected_document_ids: list[uuid.UUID]
    retrieved_document_ids: list[uuid.UUID]
    hit: bool
    reciprocal_rank: float


@dataclass(frozen=True)
class EvaluationResult:
    run: EvaluationRun
    hit_rate: float
    mean_reciprocal_rank: float
    cases: list[EvaluationCaseResult]


def register_user(session: Session, *, email: str, password: str) -> User:
    if session.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("an account with that email already exists")
    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("an account with that email already exists") from exc
    return user


def authenticate_user(session: Session, *, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        consume_dummy_password_check(password)
        raise InvalidCredentialsError("invalid email or password")

    valid, updated_hash = verify_password(password, user.password_hash)
    if not valid:
        raise InvalidCredentialsError("invalid email or password")
    if updated_hash is not None:
        user.password_hash = updated_hash
        session.commit()
    return user


def ingest_document(
    session: Session,
    *,
    user_id: uuid.UUID,
    metadata: DocumentMetadata,
    content: bytes,
    settings: Settings,
    embedding: DeterministicEmbedding,
) -> Document:
    sections = parse_document(
        content,
        metadata.extension,
        max_chars=settings.parsed_content_max_chars,
    )
    drafts = chunk_sections(
        sections,
        max_chars=settings.chunk_size_chars,
        overlap_chars=settings.chunk_overlap_chars,
    )
    document = Document(
        user_id=user_id,
        filename=metadata.filename,
        media_type=metadata.media_type,
        status="ready",
        chunk_count=len(drafts),
    )
    document.chunks = [
        Chunk(
            position=draft.position,
            page=draft.page,
            text=draft.text,
            embedding=embedding.embed(draft.text),
        )
        for draft in drafts
    ]
    session.add(document)
    session.commit()
    return document


def list_documents(session: Session, *, user_id: uuid.UUID) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc(), Document.id)
        )
    )


def delete_document(
    session: Session,
    *,
    user_id: uuid.UUID,
    document_id: uuid.UUID,
) -> None:
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
    )
    if document is None:
        raise ResourceNotFoundError("document not found")
    session.delete(document)
    session.commit()


def create_conversation(
    session: Session,
    *,
    user_id: uuid.UUID,
    title: str,
) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title)
    session.add(conversation)
    session.commit()
    return conversation


def list_conversations(session: Session, *, user_id: uuid.UUID) -> list[Conversation]:
    return list(
        session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc(), Conversation.id)
        )
    )


def _owned_conversation(
    session: Session,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Conversation:
    conversation = session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise ResourceNotFoundError("conversation not found")
    return conversation


def list_messages(
    session: Session,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> list[Message]:
    _owned_conversation(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    return list(
        session.scalars(
            select(Message)
            .options(selectinload(Message.citations))
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )
    )


def send_message(
    session: Session,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    top_k: int,
    retriever: HybridRetriever,
    provider: AnswerProvider,
) -> Message:
    conversation = _owned_conversation(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    user_message = Message(conversation=conversation, role="user", content=content)
    session.add(user_message)
    session.flush()

    hits = retriever.search(
        session,
        user_id=user_id,
        query=content,
        top_k=top_k,
    )
    if hits:
        answer = provider.answer(content, hits)
    else:
        answer = LocalExtractiveProvider().answer(content, [])

    assistant = Message(
        conversation=conversation,
        role="assistant",
        content=answer.content,
    )
    session.add(assistant)
    session.flush()
    for citation_index in answer.citation_indices:
        if citation_index < 1 or citation_index > len(hits):
            continue
        hit = hits[citation_index - 1]
        assistant.citations.append(
            MessageCitation(
                citation_index=citation_index,
                document_id=hit.document_id,
                chunk_id=hit.chunk_id,
                filename=hit.filename,
                page=hit.page,
                excerpt=hit.text[:360].strip(),
            )
        )
    session.commit()
    return assistant


def run_retrieval_evaluation(
    session: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    top_k: int,
    cases: list[EvaluationCaseInput],
    retriever: HybridRetriever,
) -> EvaluationResult:
    expected_ids = {document_id for case in cases for document_id in case.expected_document_ids}
    owned_ids = set(
        session.scalars(
            select(Document.id).where(
                Document.user_id == user_id,
                Document.id.in_(expected_ids),
            )
        )
    )
    if owned_ids != expected_ids:
        raise ResourceNotFoundError("one or more expected documents were not found")

    results: list[EvaluationCaseResult] = []
    for case in cases:
        hits = retriever.search(
            session,
            user_id=user_id,
            query=case.query,
            top_k=top_k,
        )
        retrieved_ids = list(dict.fromkeys(hit.document_id for hit in hits))
        expected = set(case.expected_document_ids)
        first_relevant_rank = next(
            (
                rank
                for rank, document_id in enumerate(retrieved_ids, start=1)
                if document_id in expected
            ),
            None,
        )
        results.append(
            EvaluationCaseResult(
                query=case.query,
                expected_document_ids=case.expected_document_ids,
                retrieved_document_ids=retrieved_ids,
                hit=first_relevant_rank is not None,
                reciprocal_rank=(
                    1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0
                ),
            )
        )

    hit_rate = sum(result.hit for result in results) / len(results)
    mean_reciprocal_rank = sum(result.reciprocal_rank for result in results) / len(results)
    request_payload: dict[str, object] = {
        "name": name,
        "top_k": top_k,
        "cases": [
            {
                "query": case.query,
                "expected_document_ids": [
                    str(document_id) for document_id in case.expected_document_ids
                ],
            }
            for case in cases
        ],
    }
    result_payload: dict[str, object] = {
        "hit_rate": hit_rate,
        "mean_reciprocal_rank": mean_reciprocal_rank,
        "cases": [
            {
                "query": result.query,
                "expected_document_ids": [
                    str(document_id) for document_id in result.expected_document_ids
                ],
                "retrieved_document_ids": [
                    str(document_id) for document_id in result.retrieved_document_ids
                ],
                "hit": result.hit,
                "reciprocal_rank": result.reciprocal_rank,
            }
            for result in results
        ],
    }
    run = EvaluationRun(
        user_id=user_id,
        name=name,
        top_k=top_k,
        request_payload=request_payload,
        result_payload=result_payload,
    )
    session.add(run)
    session.commit()
    return EvaluationResult(
        run=run,
        hit_rate=hit_rate,
        mean_reciprocal_rank=mean_reciprocal_rank,
        cases=results,
    )
