from __future__ import annotations

import uuid
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class SearchHit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int | None
    text: str
    score: float


def reciprocal_rank_fusion(
    rankings: list[list[SearchHit]],
    *,
    limit: int,
    constant: int = 60,
) -> list[SearchHit]:
    """Fuse rankings without making incomparable source scores commensurate."""

    scores: dict[uuid.UUID, float] = {}
    best_rank: dict[uuid.UUID, int] = {}
    hits: dict[uuid.UUID, SearchHit] = {}
    for ranking in rankings:
        seen: set[uuid.UUID] = set()
        for rank, hit in enumerate(ranking, start=1):
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            hits.setdefault(hit.chunk_id, hit)
            best_rank[hit.chunk_id] = min(rank, best_rank.get(hit.chunk_id, rank))
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (constant + rank)

    ordered_ids = sorted(
        scores,
        key=lambda chunk_id: (
            -scores[chunk_id],
            best_rank[chunk_id],
            str(chunk_id),
        ),
    )
    return [replace(hits[chunk_id], score=scores[chunk_id]) for chunk_id in ordered_ids[:limit]]
