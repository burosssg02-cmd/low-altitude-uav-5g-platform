import numpy as np
import pytest

from rag.document_loader import (
    KnowledgeChunk,
)

from rag.hybrid_retriever import (
    HybridRetriever,
)

from rag.retriever import (
    BM25Retriever,
)

from rag.vector_retriever import (
    VectorRetriever,
)


class FakeEmbedder:
    @staticmethod
    def _embed(
        text: str,
    ) -> np.ndarray:
        text = text.lower()

        vector = np.zeros(
            3,
            dtype=float,
        )

        if (
            "rsrp" in text
            or "radio" in text
            or "signal" in text
        ):
            vector[0] += 1.0

        if (
            "llm" in text
            or "px4" in text
            or "flight control" in text
        ):
            vector[1] += 1.0

        if (
            "replan" in text
            or "rerout" in text
            or "route replacement" in text
        ):
            vector[2] += 1.0

        return vector

    def embed_documents(
        self,
        texts,
    ):
        return np.asarray(
            [
                self._embed(text)
                for text in texts
            ],
            dtype=float,
        )

    def embed_query(
        self,
        text,
    ):
        return self._embed(
            text
        )


@pytest.fixture
def chunks():
    return [
        KnowledgeChunk(
            chunk_id="radio:0001",
            source="radio.md",
            section="RSRP",
            content=(
                "Low RSRP indicates weak "
                "radio signal strength."
            ),
        ),
        KnowledgeChunk(
            chunk_id="agent:0001",
            source="agent.md",
            section="Agent safety",
            content=(
                "The LLM must not directly "
                "control PX4 flight."
            ),
        ),
        KnowledgeChunk(
            chunk_id="replan:0001",
            source="replan.md",
            section="Runtime replanning",
            content=(
                "Communication degradation "
                "may trigger runtime route "
                "replacement and replanning."
            ),
        ),
    ]


@pytest.fixture
def retriever(
    chunks,
):
    bm25 = BM25Retriever(
        chunks
    )

    vector = VectorRetriever(
        chunks,
        FakeEmbedder(),
    )

    return HybridRetriever(
        bm25,
        vector,
    )


def test_hybrid_rsrp_query(
    retriever,
):
    results = retriever.search(
        "weak RSRP signal",
        top_k=1,
    )

    assert (
        results[0].chunk.chunk_id
        == "radio:0001"
    )


def test_hybrid_llm_px4_query(
    retriever,
):
    results = retriever.search(
        "LLM PX4 flight control",
        top_k=1,
    )

    assert (
        results[0].chunk.chunk_id
        == "agent:0001"
    )


def test_hybrid_semantic_replan_query(
    retriever,
):
    results = retriever.search(
        "runtime rerouting",
        top_k=1,
    )

    assert (
        results[0].chunk.chunk_id
        == "replan:0001"
    )


def test_hybrid_merges_duplicate_chunks(
    retriever,
):
    results = retriever.search(
        "RSRP radio signal",
        top_k=3,
    )

    chunk_ids = [
        result.chunk.chunk_id
        for result in results
    ]

    assert len(
        chunk_ids
    ) == len(
        set(chunk_ids)
    )

    top = results[0]

    assert (
        top.bm25_rank is not None
    )

    assert (
        top.vector_rank is not None
    )


def test_empty_query_returns_empty(
    retriever,
):
    assert (
        retriever.search("   ")
        == []
    )


def test_invalid_top_k(
    retriever,
):
    with pytest.raises(
        ValueError,
        match="top_k must be positive",
    ):
        retriever.search(
            "RSRP",
            top_k=0,
        )
