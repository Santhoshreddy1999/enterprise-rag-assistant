# ADR 0002: pgvector Hybrid Retrieval

- **Status:** Accepted for the MVP
- **Date:** 2026-11-09
- **Implementation status:** In progress

## Context

Grounded answers need useful source chunks for both natural-language similarity
and exact terms such as product names, policy codes, and dates. A vector-only
search can miss exact lexical matches; a lexical-only search can miss
paraphrases.

The project already needs PostgreSQL for users, ownership, documents,
conversations, citations, and evaluation state. The MVP should remain
deployable as one database-backed application and support an SQLite-compatible
automated test path.

The default embedding is intentionally deterministic and local. It provides
repeatability and offline operation, not a claim of state-of-the-art semantic
quality.

## Decision

Use hybrid retrieval:

1. Normalize and deterministically chunk document text.
2. Generate and store an embedding for each chunk.
3. In PostgreSQL, produce semantic candidates using pgvector cosine distance.
4. Produce lexical candidates using PostgreSQL full-text ranking.
5. Apply the authenticated user's ownership predicate to both candidate
   queries.
6. Combine the independent rankings with reciprocal rank fusion.
7. Select a bounded `top_k` and retain chunk identity and source metadata for
   citations.

For ranked lists \(L\), reciprocal rank fusion scores a document or chunk \(d\)
as:

```text
RRF(d) = sum over L of 1 / (k + rank_L(d))
```

The fusion constant, candidate-pool sizes, tie-breaking, text-search
configuration, and maximum `top_k` must be explicit in code and covered by
tests. This ADR does not invent values that the implementation specification
does not define.

The SQLite-compatible test path computes cosine similarity and token-overlap
lexical scores in application code, then uses the same fusion and citation
behavior. PostgreSQL integration tests remain necessary because SQLite cannot
validate pgvector operators, indexes, or PostgreSQL full-text ranking.

## Rationale

Reciprocal rank fusion combines ranks instead of raw scores. Vector distance
and text-search rank have different scales, so rank fusion avoids pretending
those scores are directly calibrated. It also gives both retrieval modes a
chance to contribute without adding a separate search service.

Keeping retrieval in PostgreSQL simplifies ownership enforcement and
operations for the MVP. It also keeps relational source metadata and chunk
identity adjacent to the retrieval query.

## Alternatives considered

### Vector search only

Rejected because exact identifiers and rare terms can be poorly represented by
the deterministic embedding. It would also make relevance more dependent on
the embedding provider.

### Lexical search only

Rejected because wording differences and paraphrases can defeat token matching.

### Weighted addition of raw vector and lexical scores

Rejected as the default because the score ranges are not naturally comparable
and would require calibration for each embedding and lexical implementation.
It may be evaluated later against a fixed benchmark.

### Dedicated search or vector infrastructure

Deferred. A separate search cluster or hosted vector database adds operational
and authorization complexity without an MVP scale requirement.

### Run all ranking in application memory

Used only for the SQLite-compatible test path. It does not scale as the
production retrieval strategy and cannot use PostgreSQL indexes.

## Security and privacy constraints

- Both candidate sources must be ownership-filtered before fusion.
- Candidate pools and `top_k` must be bounded.
- Queries must be parameterized, including full-text input.
- Retrieved excerpts are untrusted document content.
- Answer providers receive only the selected, bounded excerpts required for
  the question.
- Citation records must reference chunks that were actually retrieved for the
  assistant response.
- Retrieval logs contain aggregate identifiers or counts, not raw query or
  excerpt text.

Filtering only after global candidate retrieval is not acceptable; it can leak
ranking information and waste candidate capacity on inaccessible data.

## Consequences

Positive consequences:

- exact-term and similarity signals complement one another;
- no additional production data service is required;
- rankings remain explainable through component ranks and citations;
- deterministic local evaluation is possible.

Costs and risks:

- PostgreSQL schema, extension, indexes, and query plans require maintenance;
- SQLite behavior is only an approximation;
- deterministic embeddings may have limited semantic recall;
- chunking and candidate-pool choices materially affect relevance;
- rank fusion requires stable tie-breaking for repeatable tests;
- embedding changes require an explicit re-embedding strategy.

## Required validation

Tests must demonstrate:

- deterministic chunking and embeddings;
- normalized vectors and expected cosine ordering;
- lexical matches for exact and punctuation-heavy terms;
- reciprocal rank fusion with duplicates and ties;
- ownership isolation in both candidate paths;
- stable citation identity after fusion;
- hit rate and mean reciprocal rank on a versioned synthetic corpus;
- equivalent fusion semantics in SQLite and PostgreSQL;
- PostgreSQL query plans and indexes appropriate to the target data size.

No relevance threshold, latency objective, index choice, or production-scale
benchmark is established by this ADR. Those remain measurable, unverified
gates rather than implicit claims.
