#!/usr/bin/env bash
# Prueba de carga fija del TP (modelo abierto): 50 req/s durante 30 s contra
# POST /extract, rotando los PDFs de tests/stress/pdfs/, con timeout de cliente de 30 s.
#
#   ./tests/stress/run_vegeta.sh
#   BASE_URL=http://127.0.0.1:8080 TASA=50 DURACION=30s ./tests/stress/run_vegeta.sh
#
# Deja el binario de resultados en tests/stress/resultados/ para volver a sacar reportes:
#   vegeta report -type=json < tests/stress/resultados/vegeta-<fecha>.bin
set -euo pipefail

cd "$(dirname "$0")"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
TASA="${TASA:-50}"
DURACION="${DURACION:-30s}"
TIMEOUT="${TIMEOUT:-30s}"
ETIQUETA="${ETIQUETA:-$(date +%Y%m%d-%H%M%S)}"

shopt -s nullglob
pdfs=(pdfs/*.pdf)
if [ ${#pdfs[@]} -eq 0 ]; then
  echo "No hay PDFs en tests/stress/pdfs/. Copiar la carpeta oficial o generarlos con:"
  echo "  uv run tests/stress/generar_pdfs.py"
  exit 1
fi

mkdir -p resultados
targets="resultados/targets-$ETIQUETA.txt"
resultado="resultados/vegeta-$ETIQUETA.bin"

# Vegeta recorre los targets en orden (round robin): una entrada por PDF.
for pdf in "${pdfs[@]}"; do
  printf 'POST %s/extract\nContent-Type: application/pdf\n@%s\n\n' "$BASE_URL" "$pdf"
done > "$targets"

echo "vegeta: ${TASA} req/s durante ${DURACION}, timeout ${TIMEOUT}, ${#pdfs[@]} PDFs, ${BASE_URL}"
vegeta attack -targets="$targets" -rate="$TASA" -duration="$DURACION" -timeout="$TIMEOUT" \
  | tee "$resultado" | vegeta report
vegeta report -type='hist[0,500ms,1s,2s,5s,10s,20s,30s]' < "$resultado"
