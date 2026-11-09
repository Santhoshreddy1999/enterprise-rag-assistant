from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO

from docx import Document as load_docx
from pypdf import PdfReader


class UnsupportedDocumentError(ValueError):
    pass


class InvalidDocumentError(ValueError):
    pass


class DocumentTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentMetadata:
    filename: str
    extension: str
    media_type: str


@dataclass(frozen=True)
class ParsedSection:
    text: str
    page: int | None = None


@dataclass(frozen=True)
class ChunkDraft:
    position: int
    text: str
    page: int | None


_CANONICAL_MEDIA_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_ACCEPTED_MEDIA_TYPES = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain", "text/x-markdown"},
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
}


def validate_document_metadata(filename: str | None, content_type: str | None) -> DocumentMetadata:
    if not filename:
        raise UnsupportedDocumentError("a filename is required")
    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    basename = "".join("_" if ord(char) < 32 else char for char in basename)
    if not basename or len(basename) > 255 or "." not in basename:
        raise UnsupportedDocumentError("invalid filename")

    extension = "." + basename.rsplit(".", maxsplit=1)[-1].lower()
    if extension not in _CANONICAL_MEDIA_TYPES:
        raise UnsupportedDocumentError("unsupported document extension")

    normalized_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized_type not in _ACCEPTED_MEDIA_TYPES[extension]:
        raise UnsupportedDocumentError("media type does not match the document extension")
    return DocumentMetadata(
        filename=basename,
        extension=extension,
        media_type=_CANONICAL_MEDIA_TYPES[extension],
    )


def parse_document(
    content: bytes,
    extension: str,
    *,
    max_chars: int,
) -> list[ParsedSection]:
    if not content:
        raise InvalidDocumentError("document is empty")

    if extension in {".txt", ".md"}:
        sections = _parse_text(content)
    elif extension == ".pdf":
        sections = _parse_pdf(content)
    elif extension == ".docx":
        sections = _parse_docx(content)
    else:
        raise UnsupportedDocumentError("unsupported document extension")

    cleaned: list[ParsedSection] = []
    character_count = 0
    for section in sections:
        text = re.sub(r"\s+", " ", section.text).strip()
        if not text:
            continue
        character_count += len(text)
        if character_count > max_chars:
            raise DocumentTooLargeError("parsed document exceeds the content limit")
        cleaned.append(ParsedSection(text=text, page=section.page))

    if not cleaned:
        raise InvalidDocumentError("document contains no extractable text")
    return cleaned


def _parse_text(content: bytes) -> list[ParsedSection]:
    if b"\x00" in content:
        raise InvalidDocumentError("text document appears to be binary")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidDocumentError("text documents must use UTF-8") from exc
    return [ParsedSection(text=text)]


def _parse_pdf(content: bytes) -> list[ParsedSection]:
    if not content.startswith(b"%PDF-"):
        raise InvalidDocumentError("invalid PDF signature")
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise InvalidDocumentError("encrypted PDFs are not supported")
        return [
            ParsedSection(text=page.extract_text() or "", page=index)
            for index, page in enumerate(reader.pages, start=1)
        ]
    except InvalidDocumentError:
        raise
    except Exception as exc:
        raise InvalidDocumentError("unable to parse PDF") from exc


def _parse_docx(content: bytes) -> list[ParsedSection]:
    buffer = BytesIO(content)
    if not zipfile.is_zipfile(buffer):
        raise InvalidDocumentError("invalid DOCX container")
    buffer.seek(0)
    try:
        with zipfile.ZipFile(buffer) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise InvalidDocumentError("invalid DOCX structure")
        buffer.seek(0)
        document = load_docx(buffer)
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                parts.extend(cell.text for cell in row.cells if cell.text.strip())
        return [ParsedSection(text="\n".join(parts))]
    except InvalidDocumentError:
        raise
    except Exception as exc:
        raise InvalidDocumentError("unable to parse DOCX") from exc


def chunk_sections(
    sections: list[ParsedSection],
    *,
    max_chars: int,
    overlap_chars: int,
) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    position = 0
    for section in sections:
        text = section.text
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                split = text.rfind(" ", start + max_chars // 2, end)
                if split > start:
                    end = split
            piece = text[start:end].strip()
            if piece:
                chunks.append(ChunkDraft(position=position, text=piece, page=section.page))
                position += 1
            if end >= len(text):
                break
            start = max(start + 1, end - overlap_chars)
    if not chunks:
        raise InvalidDocumentError("document contains no extractable text")
    return chunks
