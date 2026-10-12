from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeChunk:
    """
    One retrievable knowledge unit.
    """

    chunk_id: str
    source: str
    section: str
    content: str


def _parse_markdown_sections(
    text: str,
) -> list[tuple[str, str]]:
    """
    Parse Markdown into heading-based sections.

    Returns:
        [
            (section_path, section_content),
            ...
        ]
    """

    sections = []

    heading_stack: list[
        tuple[int, str]
    ] = []

    current_lines: list[str] = []
    current_section = "Document"

    def flush():
        nonlocal current_lines

        content = "\n".join(
            current_lines
        ).strip()

        if content:
            sections.append(
                (
                    current_section,
                    content,
                )
            )

        current_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        stripped = line.lstrip()

        if stripped.startswith("#"):
            prefix = (
                len(stripped)
                - len(
                    stripped.lstrip("#")
                )
            )

            if (
                prefix >= 1
                and prefix <= 6
                and len(stripped) > prefix
                and stripped[prefix] == " "
            ):
                flush()

                title = (
                    stripped[
                        prefix + 1:
                    ]
                    .strip()
                )

                while (
                    heading_stack
                    and heading_stack[-1][0]
                    >= prefix
                ):
                    heading_stack.pop()

                heading_stack.append(
                    (
                        prefix,
                        title,
                    )
                )

                current_section = (
                    " > ".join(
                        item[1]
                        for item
                        in heading_stack
                    )
                )

                continue

        current_lines.append(
            line
        )

    flush()

    return sections


def _split_long_text(
    text: str,
    max_chars: int,
) -> list[str]:
    """
    Split one section into paragraph-aware chunks.
    """

    paragraphs = [
        paragraph.strip()
        for paragraph
        in text.split("\n\n")
        if paragraph.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            candidate = paragraph
        else:
            candidate = (
                current
                + "\n\n"
                + paragraph
            )

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(
                current.strip()
            )
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        # Fallback for an unusually long paragraph.
        start = 0

        while start < len(paragraph):
            end = min(
                start + max_chars,
                len(paragraph),
            )

            piece = (
                paragraph[
                    start:end
                ]
                .strip()
            )

            if piece:
                chunks.append(
                    piece
                )

            start = end

    if current:
        chunks.append(
            current.strip()
        )

    return chunks


def load_markdown_file(
    path: Path,
    *,
    max_chars: int = 900,
) -> list[KnowledgeChunk]:
    """
    Load one Markdown knowledge file and
    convert it into structured chunks.
    """

    path = Path(
        path
    )

    if max_chars <= 0:
        raise ValueError(
            "max_chars must be positive"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    sections = (
        _parse_markdown_sections(
            text
        )
    )

    result = []

    chunk_number = 0

    for section, content in sections:
        pieces = _split_long_text(
            content,
            max_chars,
        )

        for piece in pieces:
            chunk_number += 1

            chunk_id = (
                f"{path.stem}:"
                f"{chunk_number:04d}"
            )

            result.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    source=path.name,
                    section=section,
                    content=piece,
                )
            )

    return result


def load_knowledge_base(
    knowledge_dir: Path,
    *,
    max_chars: int = 900,
) -> list[KnowledgeChunk]:
    """
    Load all Markdown files under a knowledge
    directory.
    """

    knowledge_dir = Path(
        knowledge_dir
    )

    if not knowledge_dir.exists():
        raise FileNotFoundError(
            f"Knowledge directory not found: "
            f"{knowledge_dir}"
        )

    markdown_files = sorted(
        knowledge_dir.glob(
            "*.md"
        )
    )

    chunks = []

    for path in markdown_files:
        chunks.extend(
            load_markdown_file(
                path,
                max_chars=max_chars,
            )
        )

    return chunks
