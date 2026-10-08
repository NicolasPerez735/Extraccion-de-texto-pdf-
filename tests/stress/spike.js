// Prueba spike del TP (modelo cerrado): subida a 100 VUs en 10 s, 20 s sostenidos y
// bajada a 0 en 10 s, contra POST /extract con el PDF binario en el body.
//
//   k6 run tests/stress/spike.js
//   k6 run -e BASE_URL=http://localhost:8080 -e PDFS=a.pdf,b.pdf tests/stress/spike.js
//
// Los PDFs se leen de tests/stress/pdfs/ (k6 no puede listar carpetas: los nombres van en
// PDFS). Cada VU rota entre ellos. Sin sleep: cada VU manda la siguiente request apenas
// recibe la respuesta, como en la prueba del profesor.
import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
const NOMBRES = (
  __ENV.PDFS ||
  "01-liviano.pdf,02-texto-80-paginas.pdf,03-capas-30-paginas.pdf,04-imagenes-9mb.pdf"
).split(",");
const PDFS = NOMBRES.map((nombre) => open(`./pdfs/${nombre}`, "b"));

export const options = {
  scenarios: {
    spike: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 100 },
        { duration: "20s", target: 100 },
        { duration: "10s", target: 0 },
      ],
    },
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "max"],
};

export default function () {
  const indice = (__VU + __ITER) % PDFS.length;
  const respuesta = http.post(`${BASE_URL}/extract`, PDFS[indice], {
    headers: { "Content-Type": "application/pdf" },
    timeout: "60s",
    tags: { pdf: NOMBRES[indice] },
  });
  check(respuesta, {
    "status 200": (r) => r.status === 200,
    "devuelve Markdown y page_count": (r) =>
      r.status === 200 && r.json("page_count") > 0 && r.json("content") !== "",
  });
}
