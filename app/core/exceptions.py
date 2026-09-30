"""Application and domain exception types."""


class DomainError(Exception):
    """Base exception for expected domain errors."""


class ContractNotConfiguredError(DomainError):
    """Raised when a use case is invoked before its shared contract exists."""
