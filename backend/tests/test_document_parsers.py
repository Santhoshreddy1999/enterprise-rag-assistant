from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.infrastructure.documents import (
    DocumentTooLargeError,
    InvalidDocumentError,
    ParsedSection,
    chunk_sections,
    parse_document,
    validate_document_metadata,
)


def _text_pdf(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
    )
    content = DecodedStreamObject()
    content.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _docx_bytes() -> bytes:
    document = Document()
    document.add_heading("Benefits", level=1)
    document.add_paragraph("The annual leave allowance is twenty five days.")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Carry-over rules apply."
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.mark.parametrize("extension", [".txt", ".md"])
def test_text_and_markdown_parsing(extension: str) -> None:
    sections = parse_document(
        b"\xef\xbb\xbf# Policy\n\nAnnual leave is 25 days.",
        extension,
        max_chars=1_000,
    )
    assert sections[0].text == "# Policy Annual leave is 25 days."


def test_pdf_and_docx_parsing() -> None:
    pdf = parse_document(_text_pdf("Annual leave is 25 days."), ".pdf", max_chars=1_000)
    assert pdf[0].page == 1
    assert "Annual leave" in pdf[0].text

    docx = parse_document(_docx_bytes(), ".docx", max_chars=1_000)
    assert "annual leave allowance" in docx[0].text
    assert "Carry-over rules apply." in docx[0].text


def test_invalid_and_excessive_documents_are_rejected() -> None:
    with pytest.raises(InvalidDocumentError):
        parse_document(b"\x00binary", ".txt", max_chars=1_000)
    with pytest.raises(InvalidDocumentError):
        parse_document(b"not-a-pdf", ".pdf", max_chars=1_000)
    with pytest.raises(DocumentTooLargeError):
        parse_document(b"x" * 1_001, ".txt", max_chars=1_000)


def test_metadata_is_path_safe_and_chunking_is_deterministic() -> None:
    metadata = validate_document_metadata(
        r"C:\fakepath\handbook.TXT",
        "text/plain; charset=utf-8",
    )
    assert metadata.filename == "handbook.TXT"
    assert metadata.extension == ".txt"

    sections = [ParsedSection(" ".join(f"word{index}" for index in range(100)), page=3)]
    first = chunk_sections(sections, max_chars=120, overlap_chars=20)
    second = chunk_sections(sections, max_chars=120, overlap_chars=20)
    assert first == second
    assert len(first) > 1
    assert all(chunk.page == 3 for chunk in first)
    assert [chunk.position for chunk in first] == list(range(len(first)))
