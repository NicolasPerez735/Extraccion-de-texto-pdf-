#!/usr/bin/env bash
# Corre las dos pruebas del TP (k6 spike y vegeta) contra el stack ya levantado y guarda
# todo en tests/stress/resultados/ con una etiqueta, para comparar configuraciones.
#
#   ./tests/stress/medir.sh 5-replicas-backpressure
#
# Entre la prueba de k6 y la de vegeta espera 20 s para que se vacíen las colas.
set -euo pipefail

cd "$(dirname "$0")"
ETIQUETA="${1:?uso: medir.sh <etiqueta>}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
mkdir -p resultados

curl -fsS "$BASE_URL/health" >/dev/null || { echo "El stack no responde en $BASE_URL"; exit 1; }

echo "== k6 spike ($ETIQUETA)"
k6 run -e BASE_URL="$BASE_URL" --summary-export "resultados/k6-$ETIQUETA.json" spike.js \
  | tee "resultados/k6-$ETIQUETA.txt"

sleep 20

echo "== vegeta 50 req/s ($ETIQUETA)"
ETIQUETA="$ETIQUETA" BASE_URL="$BASE_URL" ./run_vegeta.sh | tee "resultados/vegeta-$ETIQUETA.txt"
