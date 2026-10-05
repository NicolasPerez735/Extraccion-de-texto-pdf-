"""HTTP contracts for PDF extraction."""

from pydantic import BaseModel


class ExtractionResponse(BaseModel):
    """Text extracted from the uploaded PDF."""

    text: str
