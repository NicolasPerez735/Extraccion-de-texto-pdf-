"""Lee los PDFs fuera del event loop, en un pool de workers, con backpressure."""

import asyncio
from collections.abc import Callable
from concurrent.futures import Executor

from app.core.exceptions import ServiceOverloadedError


class PoolLectorPaginas:
    """Separa el runtime HTTP de la lectura del PDF: el event loop sigue atendiendo
    requests mientras los workers del pool leen. En producción el pool es de
    procesos, porque la lectura usa CPU y no libera el GIL. Lo comparten /extraer y
    /extract.

    Backpressure: a lo sumo `en_paralelo` lecturas a la vez (una por worker) y
    `cola_maxima` esperando lugar. Si la cola está llena, o alguien espera más de
    `espera_maxima_segundos`, se rechaza con ServiceOverloadedError: un 503 rápido es
    mejor que una request que igual va a vencer en el cliente."""

    def __init__(
        self,
        leer: Callable[[bytes], list[str]],
        executor: Executor,
        en_paralelo: int,
        cola_maxima: int,
        espera_maxima_segundos: float,
    ) -> None:
        self._leer = leer
        self._executor = executor
        self._lugares = asyncio.Semaphore(en_paralelo)
        self._cola_maxima = cola_maxima
        self._esperando = 0
        self._espera_maxima = espera_maxima_segundos

    async def leer(self, contenido: bytes) -> list[str]:
        await self._ocupar_lugar()
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, self._leer, contenido)
        finally:
            self._lugares.release()

    async def _ocupar_lugar(self) -> None:
        if self._lugares.locked() and self._esperando >= self._cola_maxima:
            raise ServiceOverloadedError("cola_llena")
        self._esperando += 1
        try:
            async with asyncio.timeout(self._espera_maxima):
                await self._lugares.acquire()
        except TimeoutError as error:
            raise ServiceOverloadedError("espera_agotada") from error
        finally:
            self._esperando -= 1

    def cerrar(self) -> None:
        self._executor.shutdown()
