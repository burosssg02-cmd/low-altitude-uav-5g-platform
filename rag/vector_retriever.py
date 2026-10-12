from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from rag.document_loader import (
    KnowledgeChunk,
    load_knowledge_base,
)


class EmbeddingProvider(Protocol):
    """
    Minimal embedding-provider interface.

    VectorRetriever depends on this interface
    rather than directly depending on a specific
    model or external API.
    """

    def embed_documents(
        self,
        texts: list[str],
    ) -> np.ndarray:
        ...

    def embed_query(
        self,
        text: str,
    ) -> np.ndarray:
        ...


class SentenceTransformerEmbedder:
    """
    Offline multilingual embedding provider.

    The default model is loaded from the local
    project model directory. The runtime does
    not silently fall back to Hugging Face.
    """

    DEFAULT_MODEL_PATH = (
        Path(__file__).resolve().parent.parent
        / "models"
        / "models"
        / (
            "sentence-transformers--"
            "paraphrase-multilingual-MiniLM-L12-v2"
        )
        / "snapshots"
        / "master"
    )

    def __init__(
        self,
        model_name: str | None = None,
    ):
        from sentence_transformers import (
            SentenceTransformer,
        )

        if model_name is None:
            model_path = (
                self.DEFAULT_MODEL_PATH
            )
        else:
            model_path = Path(
                model_name
            ).expanduser()

        model_path = (
            model_path.resolve()
        )

        if not model_path.exists():
            raise FileNotFoundError(
                "Local embedding model not found: "
                f"{model_path}"
            )

        self.model_name = str(
            model_path
        )

        self.model = SentenceTransformer(
            self.model_name,
            device="cpu",
            local_files_only=True,
        )

    def embed_documents(
        self,
        texts: list[str],
    ) -> np.ndarray:
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embeddings,
            dtype=float,
        )

    def embed_query(
        self,
        text: str,
    ) -> np.ndarray:
        embedding = self.model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        return np.asarray(
            embedding,
            dtype=float,
        )


@dataclass(frozen=True)
class VectorRetrievalResult:
    chunk: KnowledgeChunk
    score: float


def _normalize_vector(
    vector: np.ndarray,
) -> np.ndarray:
    vector = np.asarray(
        vector,
        dtype=float,
    )

    norm = np.linalg.norm(
        vector
    )

    if norm <= 0:
        return vector

    return vector / norm


def _normalize_matrix(
    matrix: np.ndarray,
) -> np.ndarray:
    matrix = np.asarray(
        matrix,
        dtype=float,
    )

    if matrix.ndim != 2:
        raise ValueError(
            "embedding matrix must be 2D"
        )

    norms = np.linalg.norm(
        matrix,
        axis=1,
        keepdims=True,
    )

    norms[
        norms == 0
    ] = 1.0

    return matrix / norms


class VectorRetriever:
    """
    In-memory cosine-similarity vector retriever.

    For the current small knowledge base this is
    intentionally simple. A persistent vector
    store can be added later without changing
    the retrieval interface.
    """

    def __init__(
        self,
        chunks: list[KnowledgeChunk],
        embedder: EmbeddingProvider,
    ):
        if not chunks:
            raise ValueError(
                "chunks must not be empty"
            )

        self.chunks = list(
            chunks
        )

        self.embedder = embedder

        texts = [
            self._chunk_text(
                chunk
            )
            for chunk in self.chunks
        ]

        embeddings = (
            self.embedder
            .embed_documents(
                texts
            )
        )

        if (
            embeddings.shape[0]
            != len(self.chunks)
        ):
            raise ValueError(
                "embedding count does not match "
                "chunk count"
            )

        self.embeddings = (
            _normalize_matrix(
                embeddings
            )
        )

    @staticmethod
    def _chunk_text(
        chunk: KnowledgeChunk,
    ) -> str:
        return (
            f"{chunk.section}\n"
            f"{chunk.content}"
        )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[
        VectorRetrievalResult
    ]:
        if top_k <= 0:
            raise ValueError(
                "top_k must be positive"
            )

        if not query.strip():
            return []

        query_embedding = (
            self.embedder.embed_query(
                query
            )
        )

        query_embedding = (
            _normalize_vector(
                query_embedding
            )
        )

        if (
            query_embedding.ndim != 1
        ):
            raise ValueError(
                "query embedding must be 1D"
            )

        if (
            query_embedding.shape[0]
            != self.embeddings.shape[1]
        ):
            raise ValueError(
                "query/document embedding "
                "dimension mismatch"
            )

        scores = (
            self.embeddings
            @ query_embedding
        )

        ranking = np.argsort(
            -scores
        )

        results = []

        for index in ranking[
            :top_k
        ]:
            results.append(
                VectorRetrievalResult(
                    chunk=self.chunks[
                        int(index)
                    ],
                    score=float(
                        scores[
                            int(index)
                        ]
                    ),
                )
            )

        return results


def build_default_vector_retriever(
    *,
    knowledge_dir: Path | None = None,
    max_chars: int = 900,
    model_name: str | None = None,
) -> VectorRetriever:
    if knowledge_dir is None:
        knowledge_dir = (
            Path(__file__).parent
            / "knowledge"
        )

    chunks = load_knowledge_base(
        knowledge_dir,
        max_chars=max_chars,
    )

    embedder = (
        SentenceTransformerEmbedder(
            model_name=model_name
        )
    )

    return VectorRetriever(
        chunks,
        embedder,
    )
