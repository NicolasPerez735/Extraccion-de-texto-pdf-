"""Application and domain exception types."""


class DomainError(Exception):
    """Base exception for expected domain errors."""

    code = "DOMAIN_ERROR"


class PdfInvalidError(DomainError):
    """Raised when the content is not a PDF (Base64 inválido, vacío o sin %PDF)."""

    code = "PDF_INVALID"


class InvalidPdfError(DomainError):
    """Raised when an uploaded file is not a readable PDF."""

    code = "INVALID_PDF"
