"""Lectura de las páginas de un PDF con PyMuPDF (MuPDF, en C)."""

import pymupdf

from app.core.exceptions import PdfCorruptedError, PdfProtectedError

# MuPDF escribe sus avisos directo a stderr, sin correlation_id. El error que importa
# se registra al responder PDF_CORRUPTED.
pymupdf.TOOLS.mupdf_display_errors(False)

MENSAJE_CORRUPTO = "El archivo PDF está corrupto."
MENSAJE_PROTEGIDO = "El archivo PDF está protegido con contraseña."


def leer_paginas(contenido: bytes) -> list[str]:
    """El texto de cada página, en orden. Es una función de módulo para poder
    ejecutarla en otro proceso (viaja por pickle). La usan los dos endpoints."""
    try:
        with pymupdf.open(stream=contenido, filetype="pdf") as documento:
            # Con contraseña de usuario MuPDF abre el archivo pero no las páginas
            # (ValueError al leerlas). Solo con la de dueño, needs_pass es False.
            if documento.needs_pass:
                raise PdfProtectedError(MENSAJE_PROTEGIDO)
            paginas = [pagina.get_text().strip() for pagina in documento]
    except RuntimeError as error:  # FileDataError hereda de RuntimeError
        raise PdfCorruptedError(MENSAJE_CORRUPTO) from error
    # Un árbol de páginas roto se abre como 0 páginas; un PDF tiene al menos una.
    if not paginas:
        raise PdfCorruptedError(MENSAJE_CORRUPTO)
    return paginas
