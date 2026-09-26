import type { Domain, QueryResponse } from "@/lib/api";

export type DomainsState =
  | { status: "loading" }
  | { status: "loaded"; domains: Domain[] }
  | { status: "error"; message: string };

export type QueryState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; response: QueryResponse };
