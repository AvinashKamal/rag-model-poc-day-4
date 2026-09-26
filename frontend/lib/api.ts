// Thin client for the RAG backend. Field names/shapes mirror
// backend/app/schemas.py (QueryRequest/QueryResponse/Citation) and the
// backend/app/main.py `/domains` handler exactly. Do not rename fields
// here without checking those files first.

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export interface Domain {
  id: string;
  display_name: string;
}

export interface Citation {
  title: string;
  source: string;
  url: string;
  domain: string;
  score: number;
}

export interface QueryResponse {
  answer: string | null;
  abstained: boolean;
  citations: Citation[];
  reasoning_note: string | null;
}

export interface QueryRequestBody {
  question: string;
  domains: string[] | null;
  top_k: number;
}

// Field-level shape guards. `res.json()` returning is not the same as the
// backend contract being honored: a top-level `Array.isArray` or
// `typeof === "object"` check lets a malformed element (missing field,
// wrong type) through, which then renders as `undefined` deep in the UI
// instead of failing loudly at the fetch boundary where the cause is
// obvious. Every field on Domain/Citation/QueryResponse is checked here.
function isDomain(value: unknown): value is Domain {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.id === "string" && typeof v.display_name === "string";
}

function isCitation(value: unknown): value is Citation {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.title === "string" &&
    typeof v.source === "string" &&
    typeof v.url === "string" &&
    typeof v.domain === "string" &&
    typeof v.score === "number"
  );
}

function isQueryResponse(value: unknown): value is QueryResponse {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    (v.answer === null || typeof v.answer === "string") &&
    typeof v.abstained === "boolean" &&
    Array.isArray(v.citations) &&
    v.citations.every(isCitation) &&
    (v.reasoning_note === null || typeof v.reasoning_note === "string")
  );
}

/** Fetches the enabled-domain list. Throws on network error, non-2xx, or a malformed body. */
export async function fetchDomains(): Promise<Domain[]> {
  const res = await fetch(`${BACKEND_URL}/domains`);
  if (!res.ok) {
    throw new Error(`Backend responded with ${res.status} fetching /domains`);
  }
  const data = await res.json();
  if (!Array.isArray(data) || !data.every(isDomain)) {
    throw new Error(
      "Malformed /domains response: expected an array of { id, display_name }"
    );
  }
  return data;
}

/** Submits a question to /query. Throws on network error, non-2xx, or a malformed body. */
export async function submitQuery(
  body: QueryRequestBody
): Promise<QueryResponse> {
  const res = await fetch(`${BACKEND_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    let detail = "";
    try {
      const errBody = await res.json();
      if (errBody && typeof errBody.detail === "string") {
        detail = `: ${errBody.detail}`;
      }
    } catch {
      // response body wasn't JSON, fall through with no extra detail
    }
    throw new Error(`Backend responded with ${res.status}${detail}`);
  }

  const data = await res.json();
  if (!isQueryResponse(data)) {
    throw new Error("Malformed /query response: unexpected shape");
  }
  return data;
}
