import asyncio
from concurrent.futures import ProcessPoolExecutor

import pytest

from app.core.exceptions import PdfCorruptedError
from app.core.pool_lector import PoolLectorPaginas
from app.core.pymupdf_paginas import leer_paginas


def test_leer_paginas_returns_the_text_of_each_page(make_pdf) -> None:
    assert leer_paginas(make_pdf("Hola", "Chau")) == ["Hola", "Chau"]


def test_leer_paginas_keeps_a_page_without_text(make_pdf) -> None:
    assert leer_paginas(make_pdf("Hola", "")) == ["Hola", ""]


def test_leer_paginas_raises_pdf_corrupted_when_mupdf_cannot_open_it() -> None:
    with pytest.raises(PdfCorruptedError):
        leer_paginas(b"%PDF-1.4\nbasura")


def test_leer_paginas_raises_pdf_corrupted_when_there_are_no_pages(make_pdf) -> None:
    # Abre bien, pero el catálogo apunta a un árbol de páginas inexistente: MuPDF lo
    # lee como un documento de 0 páginas en lugar de fallar.
    pdf = make_pdf("Hola").replace(b"/Pages 2 0 R", b"/Pages 9 0 R")

    with pytest.raises(PdfCorruptedError):
        leer_paginas(pdf)


def test_the_reading_runs_in_another_process(make_pdf) -> None:
    # Producción usa un pool de procesos: la función y sus errores tienen que poder
    # viajar entre procesos (pickle).
    async def leer_en_otro_proceso():
        with ProcessPoolExecutor(max_workers=1) as executor:
            lector = PoolLectorPaginas(
                leer_paginas,
                executor,
                en_paralelo=1,
                cola_maxima=1,
                espera_maxima_segundos=10,
            )
            paginas = await lector.leer(make_pdf("Hola"))
            with pytest.raises(PdfCorruptedError):
                await lector.leer(b"%PDF-1.4\nbasura")
            return paginas

    assert asyncio.run(leer_en_otro_proceso()) == ["Hola"]
