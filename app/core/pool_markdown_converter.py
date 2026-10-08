"""Ejecuta la conversión fuera del event loop, en un pool de workers."""

import asyncio
from collections.abc import Callable
from concurrent.futures import Executor

from app.models.extraction import DocumentoMarkdown


class PoolMarkdownConverter:
    """Separa el runtime HTTP de la conversión: el event loop sigue atendiendo
    requests mientras los workers del pool convierten. En producción el pool es de
    procesos, porque la conversión usa CPU y no libera el GIL."""

    def __init__(
        self, convertir: Callable[[bytes], DocumentoMarkdown], executor: Executor
    ) -> None:
        self._convertir = convertir
        self._executor = executor

    async def convertir(self, contenido: bytes) -> DocumentoMarkdown:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._convertir, contenido)

    def cerrar(self) -> None:
        self._executor.shutdown()
