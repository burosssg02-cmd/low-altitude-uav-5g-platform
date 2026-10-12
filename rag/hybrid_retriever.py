from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rag.document_loader import (
    KnowledgeChunk,
    load_knowledge_base,
)

from rag.retriever import (
    BM25Retriever,
)

from rag.vector_retriever import (
    SentenceTransformerEmbedder,
    VectorRetriever,
)


@dataclass(frozen=True)
class HybridRetrievalResult:
    chunk: KnowledgeChunk
    score: float

    bm25_rank: int | None
    vector_rank: int | None

    bm25_score: float | None
    vector_score: float | None


class HybridRetriever:
    """
    Hybrid lexical + semantic retriever.

    Ranking is fused with Reciprocal Rank
    Fusion (RRF), avoiding direct comparison
    between BM25 scores and cosine similarity.
    """

    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        vector_retriever: VectorRetriever,
        *,
        bm25_weight: float = 1.0,
        vector_weight: float = 1.0,
        rrf_k: float = 60.0,
    ):
        if bm25_weight < 0:
            raise ValueError(
                "bm25_weight must be non-negative"
            )

        if vector_weight < 0:
            raise ValueError(
                "vector_weight must be non-negative"
            )

        if (
            bm25_weight == 0
            and vector_weight == 0
        ):
            raise ValueError(
                "at least one retrieval weight "
                "must be positive"
            )

        if rrf_k <= 0:
            raise ValueError(
                "rrf_k must be positive"
            )

        self.bm25_retriever = (
            bm25_retriever
        )

        self.vector_retriever = (
            vector_retriever
        )

        self.bm25_weight = float(
            bm25_weight
        )

        self.vector_weight = float(
            vector_weight
        )

        self.rrf_k = float(
            rrf_k
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        candidate_k: int | None = None,
    ) -> list[HybridRetrievalResult]:
        if top_k <= 0:
            raise ValueError(
                "top_k must be positive"
            )

        if not query.strip():
            return []

        if candidate_k is None:
            candidate_k = max(
                10,
                top_k * 3,
            )

        if candidate_k <= 0:
            raise ValueError(
                "candidate_k must be positive"
            )

        bm25_results = (
            self.bm25_retriever.search(
                query,
                top_k=candidate_k,
            )
        )

        vector_results = (
            self.vector_retriever.search(
                query,
                top_k=candidate_k,
            )
        )

        merged: dict[
            str,
            dict,
        ] = {}

        for rank, result in enumerate(
            bm25_results,
            start=1,
        ):
            chunk_id = (
                result.chunk.chunk_id
            )

            record = merged.setdefault(
                chunk_id,
                {
                    "chunk": result.chunk,
                    "score": 0.0,
                    "bm25_rank": None,
                    "vector_rank": None,
                    "bm25_score": None,
                    "vector_score": None,
                },
            )

            record["score"] += (
                self.bm25_weight
                / (
                    self.rrf_k
                    + rank
                )
            )

            record["bm25_rank"] = rank
            record["bm25_score"] = (
                result.score
            )

        for rank, result in enumerate(
            vector_results,
            start=1,
        ):
            # Do not reward completely unrelated
            # zero/negative cosine candidates.
            if result.score <= 0:
                continue

            chunk_id = (
                result.chunk.chunk_id
            )

            record = merged.setdefault(
                chunk_id,
                {
                    "chunk": result.chunk,
                    "score": 0.0,
                    "bm25_rank": None,
                    "vector_rank": None,
                    "bm25_score": None,
                    "vector_score": None,
                },
            )

            record["score"] += (
                self.vector_weight
                / (
                    self.rrf_k
                    + rank
                )
            )

            record["vector_rank"] = rank
            record["vector_score"] = (
                result.score
            )

        results = [
            HybridRetrievalResult(
                chunk=record["chunk"],
                score=float(
                    record["score"]
                ),
                bm25_rank=record[
                    "bm25_rank"
                ],
                vector_rank=record[
                    "vector_rank"
                ],
                bm25_score=record[
                    "bm25_score"
                ],
                vector_score=record[
                    "vector_score"
                ],
            )
            for record in merged.values()
        ]

        results.sort(
            key=lambda result: (
                -result.score,
                result.chunk.chunk_id,
            )
        )

        return results[
            :top_k
        ]


def build_default_hybrid_retriever(
    *,
    knowledge_dir: Path | None = None,
    max_chars: int = 900,
    model_name: str | None = None,
) -> HybridRetriever:
    if knowledge_dir is None:
        knowledge_dir = (
            Path(__file__).parent
            / "knowledge"
        )

    chunks = load_knowledge_base(
        knowledge_dir,
        max_chars=max_chars,
    )

    bm25_retriever = (
        BM25Retriever(
            chunks
        )
    )

    embedder = (
        SentenceTransformerEmbedder(
            model_name=model_name
        )
    )

    vector_retriever = (
        VectorRetriever(
            chunks,
            embedder,
        )
    )

    return HybridRetriever(
        bm25_retriever,
        vector_retriever,
    )
