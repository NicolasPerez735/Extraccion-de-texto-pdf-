from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    detail: str
    correlation_id: str
