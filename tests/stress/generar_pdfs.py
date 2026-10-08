# /// script
# requires-python = ">=3.11"
# dependencies = ["reportlab", "pillow"]
# ///
"""Genera los 4 PDFs de prueba de carga en tests/stress/pdfs/.

Reemplazan a la carpeta oficial del profesor mientras no la tengamos: si se copia esa
carpeta en tests/stress/pdfs/, los scripts de k6 y vegeta la usan sin cambios.
Los cuatro van de liviano a ~9 MB con imágenes, como pide el TP. Son siempre los mismos
bytes (semilla fija), así las mediciones se pueden repetir.

Uso, desde la raíz del repo: uv run tests/stress/generar_pdfs.py
"""

import random
from io import BytesIO
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

SALIDA = Path(__file__).parent / "pdfs"
PARRAFO = (
    "El microservicio de extraccion recibe un PDF, extrae el texto de cada pagina y lo "
    "devuelve como Markdown. Las pruebas de carga miden su latencia y su throughput. "
)


def escribir_texto(pdf: canvas.Canvas, titulo: str, lineas: int) -> None:
    _, alto = A4
    y = alto - 60
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, titulo)
    pdf.setFont("Helvetica", 9)
    for linea in range(lineas):
        y -= 13
        inicio = (linea * 7) % len(PARRAFO)
        pdf.drawString(50, y, (PARRAFO * 2)[inicio : inicio + 95])


def dibujar_capas(pdf: canvas.Canvas, azar: random.Random) -> None:
    """Gráficos vectoriales: cientos de figuras que el extractor tiene que recorrer."""
    for _ in range(300):
        pdf.setStrokeColorRGB(azar.random(), azar.random(), azar.random())
        x, y = azar.uniform(40, 550), azar.uniform(40, 800)
        pdf.rect(x, y, azar.uniform(5, 40), azar.uniform(5, 40))
        pdf.line(x, y, azar.uniform(40, 550), azar.uniform(40, 800))


def imagen_ruido(azar: random.Random, lado: int) -> ImageReader:
    """Imagen de ruido: no se comprime, así que pesa lo mismo dentro del PDF."""
    imagen = Image.frombytes("RGB", (lado, lado), azar.randbytes(lado * lado * 3))
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def generar(nombre: str, paginas: int, lineas: int, capas: bool, imagenes: int) -> None:
    azar = random.Random(nombre)
    pdf = canvas.Canvas(str(SALIDA / nombre), pagesize=A4)
    for pagina in range(1, paginas + 1):
        if capas:
            dibujar_capas(pdf, azar)
        if pagina <= imagenes:
            pdf.drawImage(imagen_ruido(azar, 915), 50, 250, width=495, height=495)
        escribir_texto(pdf, f"{nombre} - pagina {pagina}", lineas)
        pdf.showPage()
    pdf.save()


def main() -> None:
    SALIDA.mkdir(exist_ok=True)
    generar("01-liviano.pdf", paginas=2, lineas=20, capas=False, imagenes=0)
    generar("02-texto-80-paginas.pdf", paginas=80, lineas=55, capas=False, imagenes=0)
    generar("03-capas-30-paginas.pdf", paginas=30, lineas=40, capas=True, imagenes=0)
    generar("04-imagenes-9mb.pdf", paginas=12, lineas=15, capas=False, imagenes=3)
    for archivo in sorted(SALIDA.glob("*.pdf")):
        print(f"{archivo.name}: {archivo.stat().st_size / 1_048_576:.2f} MB")


if __name__ == "__main__":
    main()
