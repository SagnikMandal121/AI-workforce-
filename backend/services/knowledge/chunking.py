from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class ChunkResult:
    chunk_index: int
    chunk_text: str
    token_count: int
    page_number: int | None = None
    heading: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    checksum: str = ""


class Chunker(Protocol):
    name: str

    def chunk(self, text: str, *, chunk_size: int, chunk_overlap: int) -> list[ChunkResult]: ...


class RecursiveChunker:
    name = "recursive"

    def chunk(self, text: str, *, chunk_size: int, chunk_overlap: int) -> list[ChunkResult]:
        clean_text = re.sub(r"\n{3,}", "\n\n", text.strip())
        if not clean_text:
            return []

        paragraphs = [paragraph.strip() for paragraph in clean_text.split("\n\n") if paragraph.strip()]
        chunks: list[ChunkResult] = []
        buffer = ""
        buffer_start_paragraph = 0

        def finalize_buffer(buffer_text: str, start_index: int, chunk_index: int) -> None:
            chunk_text = buffer_text.strip()
            if not chunk_text:
                return
            heading = self._extract_heading(chunk_text)
            checksum = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            chunks.append(
                ChunkResult(
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    token_count=max(len(chunk_text.split()), 1),
                    page_number=start_index + 1,
                    heading=heading,
                    metadata={"paragraph_start": start_index},
                    checksum=checksum,
                )
            )

        chunk_index = 0
        for paragraph_index, paragraph in enumerate(paragraphs):
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) <= chunk_size:
                if not buffer:
                    buffer_start_paragraph = paragraph_index
                buffer = candidate
                continue

            finalize_buffer(buffer, buffer_start_paragraph, chunk_index)
            chunk_index += 1

            words = paragraph.split()
            step = max(chunk_size - chunk_overlap, 1)
            start = 0
            while start < len(words):
                piece_words = words[start : start + chunk_size]
                piece = " ".join(piece_words).strip()
                if piece:
                    checksum = hashlib.sha256(piece.encode("utf-8")).hexdigest()
                    chunks.append(
                        ChunkResult(
                            chunk_index=chunk_index,
                            chunk_text=piece,
                            token_count=max(len(piece_words), 1),
                            page_number=paragraph_index + 1,
                            heading=self._extract_heading(piece),
                            metadata={"paragraph_start": paragraph_index, "offset": start},
                            checksum=checksum,
                        )
                    )
                    chunk_index += 1
                start += step
            buffer = ""
            buffer_start_paragraph = paragraph_index + 1

        if buffer:
            finalize_buffer(buffer, buffer_start_paragraph, chunk_index)

        return chunks

    def _extract_heading(self, text: str) -> str | None:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip() or None
        return None

