import asyncio
from concurrent.futures import ProcessPoolExecutor

import pytest

from app.core.exceptions import PdfCorruptedError
from app.core.pool_markdown_converter import PoolMarkdownConverter
from app.core.pymupdf_markdown import pdf_a_markdown
from app.models.extraction import DocumentoMarkdown


def test_pdf_a_markdown_writes_one_heading_per_page(make_pdf) -> None:
    documento = pdf_a_markdown(make_pdf("Hola", "Chau"))

    assert documento == DocumentoMarkdown(
        content="## Página 1\n\nHola\n\n## Página 2\n\nChau", page_count=2
    )


def test_pdf_a_markdown_raises_pdf_corrupted_when_mupdf_cannot_open_it() -> None:
    with pytest.raises(PdfCorruptedError):
        pdf_a_markdown(b"%PDF-1.4\nbasura")


def test_the_conversion_runs_in_another_process(make_pdf) -> None:
    # Producción usa un pool de procesos: la función y sus errores tienen que poder
    # viajar entre procesos (pickle).
    async def convertir_en_otro_proceso():
        with ProcessPoolExecutor(max_workers=1) as executor:
            converter = PoolMarkdownConverter(
                pdf_a_markdown,
                executor,
                en_paralelo=1,
                cola_maxima=1,
                espera_maxima_segundos=10,
            )
            documento = await converter.convertir(make_pdf("Hola"))
            with pytest.raises(PdfCorruptedError):
                await converter.convertir(b"%PDF-1.4\nbasura")
            return documento

    documento = asyncio.run(convertir_en_otro_proceso())

    assert documento.page_count == 1
