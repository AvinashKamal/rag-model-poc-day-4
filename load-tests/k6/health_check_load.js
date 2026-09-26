import http from "k6/http";
import { check, sleep } from "k6";

// Load test against the real retrieval pipeline: POST /query now exists
// (backend/app/main.py) and runs embed -> Qdrant search -> rerank -> LLM
// synthesis per call, so this exercises the actual TEI/Qdrant/OpenRouter
// path instead of the liveness-only /health endpoint. The p(95)<500ms
// threshold below no longer applies to that path (a synthesis call through
// an LLM is never sub-second) — raised accordingly; see the comment next to
// `thresholds`.
export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "1m", target: 10 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    // 15s: generous headroom above a single-turn LLM synthesis call over a
    // handful of reranked abstracts (see backend/app/clients/llm_client.py's
    // own 60s read timeout) — this is a p95 load-test budget, not a claim
    // about typical latency, so it's set below the client timeout but well
    // above a normal successful response.
    http_req_duration: ["p(95)<15000"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

// Fixed domain/question pair: this is a load test (throughput/latency under
// concurrency), not a retrieval-quality eval (that's eval/run_eval.py) — a
// realistic, always-answerable question is enough to exercise the full
// embed/search/rerank/LLM path per request.
const PAYLOAD = JSON.stringify({
  question: "What does the corpus say about renewable energy storage?",
  domains: ["energy"],
  top_k: 5,
});

const HEADERS = { headers: { "Content-Type": "application/json" } };

export default function () {
  const res = http.post(`${BASE_URL}/query`, PAYLOAD, HEADERS);
  check(res, {
    "status is 200": (r) => r.status === 200,
  });
  sleep(1);
}
