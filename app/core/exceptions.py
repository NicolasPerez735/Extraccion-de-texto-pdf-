"""Application and domain exception types."""


class DomainError(Exception):
    """Base exception for expected domain errors."""

    code = "DOMAIN_ERROR"


class InvalidPdfError(DomainError):
    """Raised when an uploaded file is not a readable PDF."""

    code = "INVALID_PDF"
