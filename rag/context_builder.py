from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RetrieverProtocol(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ):
        ...


@dataclass(frozen=True)
class RAGContext:
    query: str
    text: str
    chunk_ids: tuple[str, ...]
    sources: tuple[str, ...]
    sections: tuple[str, ...]


def build_rag_context(
    query: str,
    retriever: RetrieverProtocol,
    *,
    top_k: int = 3,
    max_chars: int = 3500,
) -> RAGContext:
    """
    Retrieve and format bounded knowledge context
    for downstream LLM use.

    The context explicitly preserves source,
    section and chunk identifiers so the LLM can
    distinguish retrieved knowledge from runtime
    incident data.
    """

    if top_k <= 0:
        raise ValueError(
            "top_k must be positive"
        )

    if max_chars <= 0:
        raise ValueError(
            "max_chars must be positive"
        )

    query = query.strip()

    if not query:
        return RAGContext(
            query="",
            text="",
            chunk_ids=(),
            sources=(),
            sections=(),
        )

    results = retriever.search(
        query,
        top_k=top_k,
    )

    blocks = []
    chunk_ids = []
    sources = []
    sections = []

    used_chars = 0

    for index, result in enumerate(
        results,
        start=1,
    ):
        chunk = result.chunk

        header = (
            f"[KNOWLEDGE {index}]\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"source: {chunk.source}\n"
            f"section: {chunk.section}\n"
            f"content:\n"
        )

        remaining = (
            max_chars
            - used_chars
        )

        if remaining <= 0:
            break

        separator = (
            "\n\n"
            if blocks
            else ""
        )

        available_content = (
            remaining
            - len(separator)
            - len(header)
        )

        if available_content <= 0:
            break

        content = chunk.content.strip()

        if len(content) > available_content:
            content = (
                content[
                    :available_content
                ]
                .rstrip()
            )

        if not content:
            break

        block = (
            separator
            + header
            + content
        )

        blocks.append(
            block
        )

        used_chars += len(
            block
        )

        chunk_ids.append(
            chunk.chunk_id
        )

        sources.append(
            chunk.source
        )

        sections.append(
            chunk.section
        )

    return RAGContext(
        query=query,
        text="".join(
            blocks
        ),
        chunk_ids=tuple(
            chunk_ids
        ),
        sources=tuple(
            sources
        ),
        sections=tuple(
            sections
        ),
    )


def build_incident_rag_query(
    context,
    fast_decision: dict,
) -> str:
    """
    Build a retrieval query from runtime incident
    state and the already-completed deterministic
    Fast Policy decision.

    This function does not make any flight-control
    decision.
    """

    event_type = getattr(
        context,
        "incident_type",
        "COMMUNICATION_DEGRADED",
    )

    rsrp_dbm = getattr(
        context,
        "rsrp_dbm",
        None,
    )

    sinr_db = getattr(
        context,
        "sinr_db",
        None,
    )

    coverage_score = getattr(
        context,
        "coverage_score",
        None,
    )

    reasons = getattr(
        context,
        "reasons",
        (),
    )

    decision = fast_decision.get(
        "decision",
        "UNKNOWN",
    )

    selected_planner = (
        fast_decision.get(
            "selected_planner",
            "UNKNOWN",
        )
    )

    triggered_rules = (
        fast_decision.get(
            "triggered_rules",
            []
        )
    )

    parts = [
        (
            "UAV communication incident "
            f"{event_type}."
        ),
        (
            "Explain radio degradation, RSRP, "
            "SINR, coverage score, runtime "
            "incident handling, communication-"
            "aware replanning, Fast Incident "
            "Policy, and LLM Advisor safety "
            "boundaries."
        ),
        (
            f"Fast Policy decision: "
            f"{decision}."
        ),
        (
            f"Selected planner: "
            f"{selected_planner}."
        ),
    ]

    if rsrp_dbm is not None:
        parts.append(
            f"RSRP: {rsrp_dbm} dBm."
        )

    if sinr_db is not None:
        parts.append(
            f"SINR: {sinr_db} dB."
        )

    if coverage_score is not None:
        parts.append(
            "Coverage score: "
            f"{coverage_score}."
        )

    if reasons:
        parts.append(
            "Incident reasons: "
            + ", ".join(
                str(item)
                for item in reasons
            )
            + "."
        )

    if triggered_rules:
        parts.append(
            "Triggered deterministic rules: "
            + ", ".join(
                str(item)
                for item
                in triggered_rules
            )
            + "."
        )

    return " ".join(
        parts
    )


def build_incident_rag_queries(
    context,
    fast_decision: dict,
) -> tuple[str, ...]:
    """
    Build several deterministic retrieval queries
    for different incident-analysis aspects.

    Multiple aspect queries reduce the chance that
    one topic dominates all Top-K retrieval slots.
    """

    rsrp_dbm = getattr(
        context,
        "rsrp_dbm",
        None,
    )

    sinr_db = getattr(
        context,
        "sinr_db",
        None,
    )

    coverage_score = getattr(
        context,
        "coverage_score",
        None,
    )

    decision = fast_decision.get(
        "decision",
        "UNKNOWN",
    )

    selected_planner = (
        fast_decision.get(
            "selected_planner",
            "UNKNOWN",
        )
    )

    radio_query = (
        "UAV communication degradation. "
        "Explain RSRP, SINR, coverage score, "
        "weak radio quality and communication "
        "recovery."
    )

    if rsrp_dbm is not None:
        radio_query += (
            f" RSRP is {rsrp_dbm} dBm."
        )

    if sinr_db is not None:
        radio_query += (
            f" SINR is {sinr_db} dB."
        )

    if coverage_score is not None:
        radio_query += (
            " Coverage score is "
            f"{coverage_score}."
        )

    policy_query = (
        "Explain deterministic Fast Incident "
        "Policy, runtime communication incident "
        "handling, communication-aware "
        "replanning, route replacement and why "
        "the runtime decision is made without "
        "waiting for an LLM. "
        f"Fast decision is {decision}. "
        f"Selected planner is "
        f"{selected_planner}."
    )

    safety_query = (
        "Explain LLM Incident Advisor safety "
        "boundaries. Why must the LLM not "
        "directly control PX4 or override the "
        "deterministic flight decision? "
        "Explain asynchronous advisory-only "
        "incident analysis."
    )

    return (
        radio_query,
        policy_query,
        safety_query,
    )


def build_incident_rag_context(
    context,
    fast_decision: dict,
    retriever: RetrieverProtocol,
    *,
    per_query_k: int = 2,
    top_k: int = 5,
    max_chars: int = 3500,
) -> RAGContext:
    """
    Build balanced incident RAG context from
    radio, policy/replanning and Advisor-safety
    retrieval aspects.
    """

    if per_query_k <= 0:
        raise ValueError(
            "per_query_k must be positive"
        )

    if top_k <= 0:
        raise ValueError(
            "top_k must be positive"
        )

    if max_chars <= 0:
        raise ValueError(
            "max_chars must be positive"
        )

    queries = (
        build_incident_rag_queries(
            context,
            fast_decision,
        )
    )

    selected_results = []
    seen_chunk_ids = set()

    # Round-robin by aspect. This prevents the
    # radio-quality query from consuming every
    # available retrieval slot.
    aspect_results = [
        retriever.search(
            query,
            top_k=per_query_k,
        )
        for query in queries
    ]

    for rank_index in range(
        per_query_k
    ):
        for results in aspect_results:
            if rank_index >= len(
                results
            ):
                continue

            result = results[
                rank_index
            ]

            chunk_id = (
                result.chunk.chunk_id
            )

            if chunk_id in seen_chunk_ids:
                continue

            seen_chunk_ids.add(
                chunk_id
            )

            selected_results.append(
                result
            )

            if (
                len(selected_results)
                >= top_k
            ):
                break

        if (
            len(selected_results)
            >= top_k
        ):
            break

    blocks = []
    chunk_ids = []
    sources = []
    sections = []

    used_chars = 0

    for index, result in enumerate(
        selected_results,
        start=1,
    ):
        chunk = result.chunk

        header = (
            f"[KNOWLEDGE {index}]\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"source: {chunk.source}\n"
            f"section: {chunk.section}\n"
            f"content:\n"
        )

        separator = (
            "\n\n"
            if blocks
            else ""
        )

        available_content = (
            max_chars
            - used_chars
            - len(separator)
            - len(header)
        )

        if available_content <= 0:
            break

        content = (
            chunk.content
            .strip()
        )

        if (
            len(content)
            > available_content
        ):
            content = (
                content[
                    :available_content
                ]
                .rstrip()
            )

        if not content:
            break

        block = (
            separator
            + header
            + content
        )

        blocks.append(
            block
        )

        used_chars += len(
            block
        )

        chunk_ids.append(
            chunk.chunk_id
        )

        sources.append(
            chunk.source
        )

        sections.append(
            chunk.section
        )

    return RAGContext(
        query="\n\n".join(
            queries
        ),
        text="".join(
            blocks
        ),
        chunk_ids=tuple(
            chunk_ids
        ),
        sources=tuple(
            sources
        ),
        sections=tuple(
            sections
        ),
    )
