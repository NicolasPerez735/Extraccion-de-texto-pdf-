"""Application and domain exception types."""


class DomainError(Exception):
    """Base exception for expected domain errors."""


class InvalidPdfError(DomainError):
    """Raised when an uploaded file is not a readable PDF."""


class UnsupportedFileTypeError(DomainError):
    """Raised when an uploaded file has an unsupported content type."""
