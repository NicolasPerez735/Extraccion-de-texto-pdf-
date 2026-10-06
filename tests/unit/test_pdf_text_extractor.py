import pytest

from app.core.exceptions import PdfCorruptedError
from app.core.pdf_text_extractor import PdfTextExtractor


def test_extracts_the_text_of_every_page(make_pdf) -> None:
    result = PdfTextExtractor().extract(make_pdf("Primera", "Segunda"))

    assert result.texto == "Primera\nSegunda"
    assert result.paginas == 2


def test_rejects_a_truncated_pdf() -> None:
    with pytest.raises(PdfCorruptedError):
        PdfTextExtractor().extract(b"%PDF-1.4\ncontenido roto")


def test_rejects_a_pdf_whose_pages_cannot_be_read(make_pdf) -> None:
    # Abre bien, pero el catálogo apunta a un árbol de páginas inexistente:
    # pypdf falla recién al recorrer las páginas.
    pdf = make_pdf("Hola").replace(b"/Pages 2 0 R", b"/Pages 9 0 R")

    with pytest.raises(PdfCorruptedError):
        PdfTextExtractor().extract(pdf)
