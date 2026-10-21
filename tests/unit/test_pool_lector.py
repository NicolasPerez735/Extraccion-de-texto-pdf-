"""Backpressure de POST /extract: en vez de acumular requests que van a vencer por
timeout, el conversor rechaza enseguida cuando la cola está llena o la espera se
hace demasiado larga."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.exceptions import ServiceOverloadedError
from app.core.pool_lector import PoolLectorPaginas


class ConversionBloqueada:
    """Doble de la conversión: no termina hasta que el test la libera."""

    def __init__(self) -> None:
        self.liberar = threading.Event()

    def __call__(self, contenido: bytes) -> list[str]:
        self.liberar.wait(timeout=5)
        return ["listo"]


def armar(conversion, cola_maxima: int, espera_maxima: float) -> PoolLectorPaginas:
    return PoolLectorPaginas(
        conversion,
        ThreadPoolExecutor(max_workers=1),
        en_paralelo=1,
        cola_maxima=cola_maxima,
        espera_maxima_segundos=espera_maxima,
    )


def rechazo_mientras_hay_una_en_curso(cola_maxima: int, espera_maxima: float):
    conversion = ConversionBloqueada()
    conversor = armar(conversion, cola_maxima, espera_maxima)

    async def escenario() -> ServiceOverloadedError:
        primera = asyncio.create_task(conversor.leer(b"a"))
        await asyncio.sleep(0.01)  # la primera ocupa el único lugar
        with pytest.raises(ServiceOverloadedError) as error:
            await conversor.leer(b"b")
        conversion.liberar.set()
        await primera
        return error.value

    try:
        return asyncio.run(escenario())
    finally:
        conversor.cerrar()


def test_rechaza_sin_esperar_cuando_la_cola_esta_llena() -> None:
    error = rechazo_mientras_hay_una_en_curso(cola_maxima=0, espera_maxima=5)

    assert error.motivo == "cola_llena"


def test_rechaza_cuando_la_espera_supera_el_maximo() -> None:
    error = rechazo_mientras_hay_una_en_curso(cola_maxima=1, espera_maxima=0.05)

    assert error.motivo == "espera_agotada"


def test_atiende_al_que_espera_cuando_se_libera_un_lugar() -> None:
    conversion = ConversionBloqueada()
    conversor = armar(conversion, cola_maxima=1, espera_maxima=5)

    async def escenario():
        primera = asyncio.create_task(conversor.leer(b"a"))
        segunda = asyncio.create_task(conversor.leer(b"b"))
        await asyncio.sleep(0.01)
        conversion.liberar.set()
        return await asyncio.gather(primera, segunda)

    try:
        resultados = asyncio.run(escenario())
    finally:
        conversor.cerrar()

    assert resultados == [["listo"], ["listo"]]
