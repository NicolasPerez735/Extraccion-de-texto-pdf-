"""Adaptador de conversión de PDF a Markdown con PyMuPDF (MuPDF, en C)."""

import pymupdf

from app.core.exceptions import PdfCorruptedError
from app.models.extraction import DocumentoMarkdown

# MuPDF escribe sus avisos directo a stderr, sin correlation_id. El error que importa
# se registra al responder PDF_CORRUPTED.
pymupdf.TOOLS.mupdf_display_errors(False)


def pdf_a_markdown(contenido: bytes) -> DocumentoMarkdown:
    """Un encabezado por página seguido de su texto. Es una función de módulo para
    poder ejecutarla en otro proceso (viaja por pickle)."""
    try:
        with pymupdf.open(stream=contenido, filetype="pdf") as documento:
            textos = [pagina.get_text().strip() for pagina in documento]
    except RuntimeError as error:  # FileDataError hereda de RuntimeError
        raise PdfCorruptedError("El archivo PDF está corrupto.") from error

    secciones = [
        f"## Página {numero}\n\n{texto}" if texto else f"## Página {numero}"
        for numero, texto in enumerate(textos, start=1)
    ]
    return DocumentoMarkdown(content="\n\n".join(secciones), page_count=len(textos))
