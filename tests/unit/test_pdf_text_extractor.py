from app.core.pdf_text_extractor import PdfTextExtractor


def test_extracts_the_text_of_every_page(make_pdf) -> None:
    result = PdfTextExtractor().extract(make_pdf("Primera", "Segunda"))

    assert result.texto == "Primera\nSegunda"
    assert result.paginas == 2
