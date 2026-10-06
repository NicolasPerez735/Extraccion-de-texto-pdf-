"""Application and domain exception types."""


class DomainError(Exception):
    """Base exception for expected domain errors."""

    code = "DOMAIN_ERROR"


class PdfInvalidError(DomainError):
    """Raised when the content is not a PDF (Base64 inválido, vacío o sin %PDF)."""

    code = "PDF_INVALID"


class PdfCorruptedError(DomainError):
    """Raised when pypdf cannot read the PDF or extract its text."""

    code = "PDF_CORRUPTED"
