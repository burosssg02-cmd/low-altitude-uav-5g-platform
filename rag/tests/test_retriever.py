from pathlib import Path

import pytest

from rag.retriever import (
    BM25Retriever,
    build_default_retriever,
    tokenize,
)


def test_tokenize_removes_common_stopwords():
    tokens = tokenize(
        "Why should the LLM control PX4?"
    )

    assert "llm" in tokens
    assert "px4" in tokens
    assert "why" not in tokens
    assert "the" not in tokens


def test_default_retriever_builds():
    retriever = (
        build_default_retriever()
    )

    assert isinstance(
        retriever,
        BM25Retriever,
    )

    assert len(
        retriever.chunks
    ) >= 2


def test_rsrp_query_retrieves_rsrp_section():
    retriever = (
        build_default_retriever()
    )

    results = retriever.search(
        "What happens when RSRP "
        "becomes too low?",
        top_k=3,
    )

    assert results

    sections = [
        result.chunk.section
        for result in results
    ]

    assert any(
        "RSRP" in section
        for section in sections
    )


def test_llm_px4_query_retrieves_agent_safety():
    retriever = (
        build_default_retriever()
    )

    results = retriever.search(
        "Why should an LLM not directly "
        "control PX4 flight?",
        top_k=5,
    )

    assert results

    combined = " ".join(
        (
            result.chunk.section
            + " "
            + result.chunk.content
        )
        for result in results
    ).lower()

    assert "llm" in combined
    assert "px4" in combined

    assert (
        "high-frequency" in combined
        or "no authority" in combined
        or "flight-control" in combined
    )


def test_search_returns_scores_and_terms():
    retriever = (
        build_default_retriever()
    )

    results = retriever.search(
        "communication degradation "
        "replanning",
        top_k=3,
    )

    assert results

    assert all(
        result.score > 0
        for result in results
    )

    assert all(
        result.matched_terms
        for result in results
    )


def test_invalid_top_k():
    retriever = (
        build_default_retriever()
    )

    with pytest.raises(
        ValueError,
        match="top_k must be positive",
    ):
        retriever.search(
            "RSRP",
            top_k=0,
        )
