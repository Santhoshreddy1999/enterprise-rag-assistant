from __future__ import annotations

import math
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.retrieval import SearchHit, reciprocal_rank_fusion
from app.infrastructure.embeddings import (
    DeterministicEmbedding,
    cosine_similarity,
    tokenize,
)
from app.infrastructure.models import Chunk, Document


class HybridRetriever:
    def __init__(
        self,
        embedding: DeterministicEmbedding,
        *,
        candidate_limit: int = 50,
        rrf_constant: int = 60,
    ) -> None:
        self.embedding = embedding
        self.candidate_limit = candidate_limit
        self.rrf_constant = rrf_constant

    def search(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        query: str,
        top_k: int,
    ) -> list[SearchHit]:
        candidate_limit = max(self.candidate_limit, top_k * 4)
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            semantic, lexical = self._postgres_rankings(
                session,
                user_id=user_id,
                query=query,
                candidate_limit=candidate_limit,
            )
        else:
            semantic, lexical = self._portable_rankings(
                session,
                user_id=user_id,
                query=query,
                candidate_limit=candidate_limit,
            )
        return reciprocal_rank_fusion(
            [semantic, lexical],
            limit=top_k,
            constant=self.rrf_constant,
        )

    def _portable_rankings(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        query: str,
        candidate_limit: int,
    ) -> tuple[list[SearchHit], list[SearchHit]]:
        rows = session.execute(
            select(Chunk, Document.id, Document.filename)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.user_id == user_id)
        ).all()
        query_embedding = self.embedding.embed(query)
        query_tokens = set(tokenize(query))

        semantic: list[SearchHit] = []
        lexical: list[SearchHit] = []
        for chunk, document_id, filename in rows:
            semantic.append(
                SearchHit(
                    chunk_id=chunk.id,
                    document_id=document_id,
                    filename=filename,
                    page=chunk.page,
                    text=chunk.text,
                    score=cosine_similarity(query_embedding, chunk.embedding),
                )
            )
            chunk_tokens = set(tokenize(chunk.text))
            overlap = len(query_tokens.intersection(chunk_tokens))
            if overlap:
                lexical_score = overlap / math.sqrt(len(query_tokens) * len(chunk_tokens))
                lexical.append(
                    SearchHit(
                        chunk_id=chunk.id,
                        document_id=document_id,
                        filename=filename,
                        page=chunk.page,
                        text=chunk.text,
                        score=lexical_score,
                    )
                )

        def rank_key(hit: SearchHit) -> tuple[float, str]:
            return (-hit.score, str(hit.chunk_id))

        semantic.sort(key=rank_key)
        lexical.sort(key=rank_key)
        return semantic[:candidate_limit], lexical[:candidate_limit]

    def _postgres_rankings(
        self,
        session: Session,
        *,
        user_id: uuid.UUID,
        query: str,
        candidate_limit: int,
    ) -> tuple[list[SearchHit], list[SearchHit]]:
        query_vector = self.embedding.embed(query)
        vector_literal = "[" + ",".join(f"{value:.9g}" for value in query_vector) + "]"
        common_params = {
            "user_id": str(user_id),
            "query": query,
            "embedding": vector_literal,
            "limit": candidate_limit,
        }
        semantic_rows = session.execute(
            text(
                """
                SELECT c.id AS chunk_id,
                       d.id AS document_id,
                       d.filename,
                       c.page,
                       c.text,
                       1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
                  FROM chunks AS c
                  JOIN documents AS d ON d.id = c.document_id
                 WHERE d.user_id = CAST(:user_id AS uuid)
                 ORDER BY c.embedding <=> CAST(:embedding AS vector), c.id
                 LIMIT :limit
                """
            ),
            common_params,
        ).mappings()
        lexical_rows = session.execute(
            text(
                """
                WITH q AS (
                    SELECT plainto_tsquery('english', :query) AS value
                )
                SELECT c.id AS chunk_id,
                       d.id AS document_id,
                       d.filename,
                       c.page,
                       c.text,
                       ts_rank_cd(
                           to_tsvector('english', c.text),
                           q.value
                       ) AS score
                  FROM chunks AS c
                  JOIN documents AS d ON d.id = c.document_id
                  CROSS JOIN q
                 WHERE d.user_id = CAST(:user_id AS uuid)
                   AND q.value @@ to_tsvector('english', c.text)
                 ORDER BY score DESC, c.id
                 LIMIT :limit
                """
            ),
            common_params,
        ).mappings()
        return (
            [self._row_to_hit(row) for row in semantic_rows],
            [self._row_to_hit(row) for row in lexical_rows],
        )

    @staticmethod
    def _row_to_hit(row: Any) -> SearchHit:
        return SearchHit(
            chunk_id=uuid.UUID(str(row["chunk_id"])),
            document_id=uuid.UUID(str(row["document_id"])),
            filename=str(row["filename"]),
            page=int(row["page"]) if row["page"] is not None else None,
            text=str(row["text"]),
            score=float(row["score"]),
        )
