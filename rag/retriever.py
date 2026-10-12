from __future__ import annotations

import math
import re

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from rag.document_loader import (
    KnowledgeChunk,
    load_knowledge_base,
)


TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9_]+"
)


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "why",
    "with",
}


def tokenize(
    text: str,
) -> list[str]:
    """
    Lightweight tokenizer for the current
    English engineering knowledge base.
    """

    tokens = [
        token.lower()
        for token
        in TOKEN_PATTERN.findall(
            text
        )
    ]

    return [
        token
        for token in tokens
        if (
            token
            and token not in STOPWORDS
        )
    ]


@dataclass(frozen=True)
class RetrievalResult:
    chunk: KnowledgeChunk
    score: float
    matched_terms: tuple[str, ...]


class BM25Retriever:
    """
    Lightweight in-process BM25 retriever.

    This is the lexical retrieval baseline used
    before vector embedding retrieval is added.
    """

    def __init__(
        self,
        chunks: list[KnowledgeChunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        section_boost: float = 1.5,
    ):
        if not chunks:
            raise ValueError(
                "chunks must not be empty"
            )

        self.chunks = list(
            chunks
        )

        self.k1 = float(
            k1
        )

        self.b = float(
            b
        )

        self.section_boost = float(
            section_boost
        )

        self._documents: list[
            list[str]
        ] = []

        self._term_frequencies: list[
            Counter
        ] = []

        self._document_frequency = Counter()

        self._section_tokens = []

        for chunk in self.chunks:
            content_tokens = tokenize(
                chunk.content
            )

            section_tokens = tokenize(
                chunk.section
            )

            self._documents.append(
                content_tokens
            )

            self._section_tokens.append(
                set(
                    section_tokens
                )
            )

            frequencies = Counter(
                content_tokens
            )

            self._term_frequencies.append(
                frequencies
            )

            for term in set(
                content_tokens
                + section_tokens
            ):
                self._document_frequency[
                    term
                ] += 1

        lengths = [
            len(document)
            for document
            in self._documents
        ]

        self._average_length = (
            sum(lengths)
            / len(lengths)
            if lengths
            else 1.0
        )

    def _idf(
        self,
        term: str,
    ) -> float:
        document_count = len(
            self.chunks
        )

        frequency = (
            self._document_frequency.get(
                term,
                0,
            )
        )

        return math.log(
            1.0
            + (
                document_count
                - frequency
                + 0.5
            )
            / (
                frequency
                + 0.5
            )
        )

    def _score_document(
        self,
        *,
        query_terms: list[str],
        document_index: int,
    ) -> tuple[
        float,
        tuple[str, ...],
    ]:
        frequencies = (
            self._term_frequencies[
                document_index
            ]
        )

        document_length = len(
            self._documents[
                document_index
            ]
        )

        section_terms = (
            self._section_tokens[
                document_index
            ]
        )

        score = 0.0
        matched = []

        for term in set(
            query_terms
        ):
            term_frequency = (
                frequencies.get(
                    term,
                    0,
                )
            )

            section_match = (
                term in section_terms
            )

            if (
                term_frequency <= 0
                and not section_match
            ):
                continue

            matched.append(
                term
            )

            idf = self._idf(
                term
            )

            if term_frequency > 0:
                denominator = (
                    term_frequency
                    + self.k1
                    * (
                        1.0
                        - self.b
                        + self.b
                        * document_length
                        / self._average_length
                    )
                )

                score += (
                    idf
                    * (
                        term_frequency
                        * (
                            self.k1
                            + 1.0
                        )
                    )
                    / denominator
                )

            if section_match:
                score += (
                    idf
                    * self.section_boost
                )

        return (
            score,
            tuple(
                sorted(
                    matched
                )
            ),
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        if top_k <= 0:
            raise ValueError(
                "top_k must be positive"
            )

        query_terms = tokenize(
            query
        )

        if not query_terms:
            return []

        results = []

        for index, chunk in enumerate(
            self.chunks
        ):
            (
                score,
                matched_terms,
            ) = self._score_document(
                query_terms=query_terms,
                document_index=index,
            )

            if score <= 0:
                continue

            results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=score,
                    matched_terms=(
                        matched_terms
                    ),
                )
            )

        results.sort(
            key=lambda result: (
                -result.score,
                result.chunk.chunk_id,
            )
        )

        return results[
            :top_k
        ]


def build_default_retriever(
    *,
    knowledge_dir: Path | None = None,
    max_chars: int = 900,
) -> BM25Retriever:
    if knowledge_dir is None:
        knowledge_dir = (
            Path(__file__).parent
            / "knowledge"
        )

    chunks = load_knowledge_base(
        knowledge_dir,
        max_chars=max_chars,
    )

    return BM25Retriever(
        chunks
    )
