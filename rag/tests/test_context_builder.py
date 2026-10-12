from types import SimpleNamespace

import pytest

from rag.context_builder import (
    build_incident_rag_query,
    build_rag_context,
)

from rag.document_loader import (
    KnowledgeChunk,
)


class FakeResult:
    def __init__(
        self,
        chunk,
    ):
        self.chunk = chunk


class FakeRetriever:
    def __init__(
        self,
        chunks,
    ):
        self.chunks = chunks
        self.last_query = None
        self.last_top_k = None

    def search(
        self,
        query,
        *,
        top_k=5,
    ):
        self.last_query = query
        self.last_top_k = top_k

        return [
            FakeResult(
                chunk
            )
            for chunk
            in self.chunks[:top_k]
        ]


def make_chunks():
    return [
        KnowledgeChunk(
            chunk_id="radio:0001",
            source="radio.md",
            section="RSRP",
            content=(
                "Low RSRP indicates weak "
                "received signal strength."
            ),
        ),
        KnowledgeChunk(
            chunk_id="agent:0001",
            source="agent.md",
            section="LLM Incident Advisor",
            content=(
                "The Advisor has no authority "
                "to directly control PX4."
            ),
        ),
    ]


def test_context_preserves_metadata():
    retriever = FakeRetriever(
        make_chunks()
    )

    result = build_rag_context(
        "RSRP and LLM safety",
        retriever,
        top_k=2,
    )

    assert result.chunk_ids == (
        "radio:0001",
        "agent:0001",
    )

    assert result.sources == (
        "radio.md",
        "agent.md",
    )

    assert "chunk_id: radio:0001" in (
        result.text
    )

    assert (
        "section: LLM Incident Advisor"
        in result.text
    )


def test_context_respects_top_k():
    retriever = FakeRetriever(
        make_chunks()
    )

    result = build_rag_context(
        "communication",
        retriever,
        top_k=1,
    )

    assert len(
        result.chunk_ids
    ) == 1

    assert (
        retriever.last_top_k
        == 1
    )


def test_context_respects_character_limit():
    chunks = [
        KnowledgeChunk(
            chunk_id="long:0001",
            source="long.md",
            section="Long",
            content="A" * 5000,
        )
    ]

    retriever = FakeRetriever(
        chunks
    )

    result = build_rag_context(
        "long knowledge",
        retriever,
        max_chars=300,
    )

    assert (
        len(result.text)
        <= 300
    )

    assert result.chunk_ids == (
        "long:0001",
    )


def test_empty_query_returns_empty_context():
    retriever = FakeRetriever(
        make_chunks()
    )

    result = build_rag_context(
        "   ",
        retriever,
    )

    assert result.text == ""
    assert result.chunk_ids == ()


def test_incident_query_contains_runtime_facts():
    context = SimpleNamespace(
        incident_type=(
            "COMMUNICATION_DEGRADED"
        ),
        rsrp_dbm=-97.9,
        sinr_db=1.9,
        coverage_score=0.491,
        reasons=(
            "LOW_RSRP",
            "LOW_COVERAGE_SCORE",
        ),
    )

    fast_decision = {
        "decision":
            "REPLAN_RECOMMENDED",
        "selected_planner":
            "communication_aware",
        "triggered_rules": [
            "MEAN_RSRP_IMPROVED",
            "MEAN_SINR_IMPROVED",
        ],
    }

    query = (
        build_incident_rag_query(
            context,
            fast_decision,
        )
    )

    assert (
        "COMMUNICATION_DEGRADED"
        in query
    )

    assert "-97.9" in query
    assert "1.9" in query
    assert "0.491" in query

    assert (
        "REPLAN_RECOMMENDED"
        in query
    )

    assert (
        "communication_aware"
        in query
    )


def test_invalid_limits():
    retriever = FakeRetriever(
        make_chunks()
    )

    with pytest.raises(
        ValueError,
        match="top_k must be positive",
    ):
        build_rag_context(
            "test",
            retriever,
            top_k=0,
        )

    with pytest.raises(
        ValueError,
        match="max_chars must be positive",
    ):
        build_rag_context(
            "test",
            retriever,
            max_chars=0,
        )


def test_incident_rag_queries_cover_three_aspects():
    from rag.context_builder import (
        build_incident_rag_queries,
    )

    context = SimpleNamespace(
        rsrp_dbm=-97.9,
        sinr_db=1.9,
        coverage_score=0.491,
    )

    fast_decision = {
        "decision":
            "REPLAN_RECOMMENDED",
        "selected_planner":
            "communication_aware",
    }

    queries = (
        build_incident_rag_queries(
            context,
            fast_decision,
        )
    )

    assert len(queries) == 3

    combined = " ".join(
        queries
    ).lower()

    assert "rsrp" in combined
    assert "fast incident policy" in combined
    assert "communication-aware" in combined
    assert "llm incident advisor" in combined
    assert "px4" in combined


class AspectAwareFakeRetriever:
    def search(
        self,
        query,
        *,
        top_k=5,
    ):
        query_lower = (
            query.lower()
        )

        if "rsrp" in query_lower:
            chunks = [
                KnowledgeChunk(
                    chunk_id="radio:1",
                    source="radio.md",
                    section="RSRP",
                    content="Radio knowledge.",
                ),
                KnowledgeChunk(
                    chunk_id="common:1",
                    source="common.md",
                    section="Runtime",
                    content="Runtime knowledge.",
                ),
            ]

        elif (
            "fast incident policy"
            in query_lower
        ):
            chunks = [
                KnowledgeChunk(
                    chunk_id="policy:1",
                    source="policy.md",
                    section="Fast Incident Policy",
                    content="Policy knowledge.",
                ),
                KnowledgeChunk(
                    chunk_id="common:1",
                    source="common.md",
                    section="Runtime",
                    content="Runtime knowledge.",
                ),
            ]

        else:
            chunks = [
                KnowledgeChunk(
                    chunk_id="advisor:1",
                    source="advisor.md",
                    section="LLM Incident Advisor",
                    content="Advisor safety knowledge.",
                )
            ]

        return [
            FakeResult(chunk)
            for chunk in chunks[
                :top_k
            ]
        ]


def test_multi_aspect_context_balances_topics():
    from rag.context_builder import (
        build_incident_rag_context,
    )

    context = SimpleNamespace(
        rsrp_dbm=-97.9,
        sinr_db=1.9,
        coverage_score=0.491,
    )

    fast_decision = {
        "decision":
            "REPLAN_RECOMMENDED",
        "selected_planner":
            "communication_aware",
    }

    result = (
        build_incident_rag_context(
            context,
            fast_decision,
            AspectAwareFakeRetriever(),
            per_query_k=2,
            top_k=4,
        )
    )

    assert "radio:1" in result.chunk_ids
    assert "policy:1" in result.chunk_ids
    assert "advisor:1" in result.chunk_ids

    assert (
        len(result.chunk_ids)
        == len(
            set(result.chunk_ids)
        )
    )


def test_multi_aspect_context_respects_limit():
    from rag.context_builder import (
        build_incident_rag_context,
    )

    context = SimpleNamespace(
        rsrp_dbm=-97.9,
        sinr_db=1.9,
        coverage_score=0.491,
    )

    result = (
        build_incident_rag_context(
            context,
            {
                "decision":
                    "REPLAN_RECOMMENDED",
                "selected_planner":
                    "communication_aware",
            },
            AspectAwareFakeRetriever(),
            max_chars=300,
        )
    )

    assert (
        len(result.text)
        <= 300
    )
