from __future__ import annotations

import csv
import hashlib
import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

from database.models.knowledge import DocumentSourceType


@dataclass(slots=True)
class ParsedDocument:
    text: str
    metadata: dict[str, object] = field(default_factory=dict)
    title: str | None = None
    page_count: int | None = None


class DocumentParser(Protocol):
    source_type: DocumentSourceType

    def parse(
        self,
        *,
        raw_bytes: bytes | None,
        content_text: str | None,
        source_uri: str | None,
        file_name: str | None,
        mime_type: str | None,
        metadata: dict[str, object],
    ) -> ParsedDocument: ...


class BaseParser(ABC):
    source_type: DocumentSourceType

    def _fallback_text(self, raw_bytes: bytes | None, content_text: str | None, source_uri: str | None) -> str:
        if content_text:
            return content_text
        if raw_bytes:
            return raw_bytes.decode("utf-8", errors="ignore")
        if source_uri:
            return source_uri
        return ""


class PlainTextParser(BaseParser):
    def __init__(self, source_type: DocumentSourceType) -> None:
        self.source_type = source_type

    def parse(
        self,
        *,
        raw_bytes: bytes | None,
        content_text: str | None,
        source_uri: str | None,
        file_name: str | None,
        mime_type: str | None,
        metadata: dict[str, object],
    ) -> ParsedDocument:
        text = self._fallback_text(raw_bytes, content_text, source_uri)
        cleaned = self._clean_text(text)
        return ParsedDocument(
            text=cleaned,
            metadata={**metadata, "parser": self.source_type.value, "file_name": file_name, "mime_type": mime_type},
            title=self._derive_title(file_name, source_uri, cleaned),
            page_count=max(cleaned.count("\n") + 1, 1),
        )

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def _derive_title(self, file_name: str | None, source_uri: str | None, text: str) -> str | None:
        if file_name:
            return file_name.rsplit(".", 1)[0]
        if source_uri:
            return source_uri.rstrip("/").rsplit("/", 1)[-1] or source_uri
        first_line = next((line.strip("# ").strip() for line in text.splitlines() if line.strip()), None)
        return first_line or None


class CsvParser(PlainTextParser):
    def __init__(self) -> None:
        super().__init__(DocumentSourceType.CSV)

    def parse(
        self,
        *,
        raw_bytes: bytes | None,
        content_text: str | None,
        source_uri: str | None,
        file_name: str | None,
        mime_type: str | None,
        metadata: dict[str, object],
    ) -> ParsedDocument:
        text = self._fallback_text(raw_bytes, content_text, source_uri)
        if raw_bytes and not content_text:
            decoded = raw_bytes.decode("utf-8", errors="ignore")
            rows = list(csv.reader(io.StringIO(decoded)))
            text = "\n".join([", ".join(row) for row in rows])
        return super().parse(
            raw_bytes=None,
            content_text=text,
            source_uri=source_uri,
            file_name=file_name,
            mime_type=mime_type,
            metadata=metadata,
        )


class UrlParser(PlainTextParser):
    def __init__(self) -> None:
        super().__init__(DocumentSourceType.WEBSITE_URL)


class BinaryPlaceholderParser(PlainTextParser):
    def __init__(self, source_type: DocumentSourceType) -> None:
        super().__init__(source_type)


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[DocumentSourceType, DocumentParser] = {
            DocumentSourceType.TXT: PlainTextParser(DocumentSourceType.TXT),
            DocumentSourceType.MARKDOWN: PlainTextParser(DocumentSourceType.MARKDOWN),
            DocumentSourceType.CSV: CsvParser(),
            DocumentSourceType.WEBSITE_URL: UrlParser(),
            DocumentSourceType.PDF: BinaryPlaceholderParser(DocumentSourceType.PDF),
            DocumentSourceType.DOCX: BinaryPlaceholderParser(DocumentSourceType.DOCX),
            DocumentSourceType.NOTION: BinaryPlaceholderParser(DocumentSourceType.NOTION),
            DocumentSourceType.GOOGLE_DRIVE: BinaryPlaceholderParser(DocumentSourceType.GOOGLE_DRIVE),
            DocumentSourceType.CONFLUENCE: BinaryPlaceholderParser(DocumentSourceType.CONFLUENCE),
        }

    def get(self, source_type: DocumentSourceType) -> DocumentParser:
        return self._parsers[source_type]

