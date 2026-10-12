from pathlib import Path

import pytest

from rag.document_loader import (
    KnowledgeChunk,
    load_knowledge_base,
    load_markdown_file,
)


def test_load_real_knowledge_base():
    chunks = load_knowledge_base(
        Path(
            "rag/knowledge"
        ),
        max_chars=900,
    )

    assert chunks

    assert all(
        isinstance(
            chunk,
            KnowledgeChunk,
        )
        for chunk in chunks
    )

    sources = {
        chunk.source
        for chunk in chunks
    }

    assert (
        "communication_incidents.md"
        in sources
    )

    assert (
        "system_architecture.md"
        in sources
    )


def test_chunks_have_metadata():
    chunks = load_knowledge_base(
        Path(
            "rag/knowledge"
        )
    )

    for chunk in chunks:
        assert chunk.chunk_id
        assert chunk.source
        assert chunk.section
        assert chunk.content


def test_heading_is_preserved(
    tmp_path,
):
    path = (
        tmp_path
        / "example.md"
    )

    path.write_text(
        """# Platform

## Communication

RSRP describes received signal strength.

## Agent

The LLM does not directly control PX4.
""",
        encoding="utf-8",
    )

    chunks = load_markdown_file(
        path
    )

    sections = [
        chunk.section
        for chunk in chunks
    ]

    assert (
        "Platform > Communication"
        in sections
    )

    assert (
        "Platform > Agent"
        in sections
    )


def test_chunk_size_limit(
    tmp_path,
):
    path = (
        tmp_path
        / "long.md"
    )

    path.write_text(
        "# Test\n\n"
        + ("A" * 250),
        encoding="utf-8",
    )

    chunks = load_markdown_file(
        path,
        max_chars=100,
    )

    assert len(chunks) == 3

    assert all(
        len(chunk.content)
        <= 100
        for chunk in chunks
    )


def test_invalid_chunk_size(
    tmp_path,
):
    path = (
        tmp_path
        / "example.md"
    )

    path.write_text(
        "# Test\n\nContent",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="max_chars must be positive",
    ):
        load_markdown_file(
            path,
            max_chars=0,
        )
