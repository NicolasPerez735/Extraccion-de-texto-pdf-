"""Formato común de errores del contrato microservicios-pdf."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict
    correlation_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
