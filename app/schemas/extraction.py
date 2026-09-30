"""HTTP contract placeholders for PDF extraction.

The shared ``microservicios-pdf v1.0.0`` contract is not present in the
repository yet. These schemas intentionally contain no speculative fields;
they are the place to add the confirmed request and response contract.
"""

from pydantic import BaseModel


class ExtractionRequest(BaseModel):
    """Request DTO to be completed from the shared contract."""


class ExtractionResponse(BaseModel):
    """Response DTO to be completed from the shared contract."""
