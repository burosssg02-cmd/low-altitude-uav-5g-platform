import numpy as np
import pytest

from rag.document_loader import (
    KnowledgeChunk,
)

from rag.vector_retriever import (
    VectorRetriever,
)


class FakeEmbedder:
    """
    Deterministic test embedder.

    Dimensions:
    0 -> radio / RSRP
    1 -> LLM / PX4
    2 -> replan
    """

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
        ):
            vector[0] += 1.0

        if (
            "llm" in text
            or "px4" in text
        ):
            vector[1] += 1.0

        if (
            "replan" in text
            or "route replacement"
            in text
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
            ]
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
            section="LLM safety",
            content=(
                "The LLM must not directly "
                "control PX4."
            ),
        ),
        KnowledgeChunk(
            chunk_id="replan:0001",
            source="replan.md",
            section="Runtime replanning",
            content=(
                "Communication degradation "
                "may trigger route replacement "
                "and replanning."
            ),
        ),
    ]


def test_vector_retriever_rsrp(
    chunks,
):
    retriever = VectorRetriever(
        chunks,
        FakeEmbedder(),
    )

    results = retriever.search(
        "weak RSRP radio link",
        top_k=1,
    )

    assert (
        results[0].chunk.chunk_id
        == "radio:0001"
    )

    assert (
        results[0].score
        > 0
    )


def test_vector_retriever_llm_px4(
    chunks,
):
    retriever = VectorRetriever(
        chunks,
        FakeEmbedder(),
    )

    results = retriever.search(
        "LLM controls PX4",
        top_k=1,
    )

    assert (
        results[0].chunk.chunk_id
        == "agent:0001"
    )


def test_vector_retriever_replan(
    chunks,
):
    retriever = VectorRetriever(
        chunks,
        FakeEmbedder(),
    )

    results = retriever.search(
        "runtime route replan",
        top_k=1,
    )

    assert (
        results[0].chunk.chunk_id
        == "replan:0001"
    )


def test_empty_query_returns_empty(
    chunks,
):
    retriever = VectorRetriever(
        chunks,
        FakeEmbedder(),
    )

    assert (
        retriever.search(
            "   "
        )
        == []
    )


def test_invalid_top_k(
    chunks,
):
    retriever = VectorRetriever(
        chunks,
        FakeEmbedder(),
    )

    with pytest.raises(
        ValueError,
        match="top_k must be positive",
    ):
        retriever.search(
            "RSRP",
            top_k=0,
        )


def test_empty_chunks_rejected():
    with pytest.raises(
        ValueError,
        match="chunks must not be empty",
    ):
        VectorRetriever(
            [],
            FakeEmbedder(),
        )
