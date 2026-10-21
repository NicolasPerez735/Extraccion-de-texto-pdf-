from typing import Protocol


class LectorPaginas(Protocol):
    async def leer(self, contenido: bytes) -> list[str]:
        """Devuelve el texto de cada página del PDF, en orden."""
