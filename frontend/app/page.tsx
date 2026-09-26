"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import styles from "@/app/page.module.css";
import DomainSelector from "@/app/components/DomainSelector";
import QuestionForm from "@/app/components/QuestionForm";
import StatusPanel from "@/app/components/StatusPanel";
import AnswerPanel from "@/app/components/AnswerPanel";
import { fetchDomains, submitQuery } from "@/lib/api";
import type { DomainsState, QueryState } from "@/app/types";

const TOP_K = 5;

export default function Home() {
  const [domainsState, setDomainsState] = useState<DomainsState>({
    status: "loading",
  });
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [queryState, setQueryState] = useState<QueryState>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    fetchDomains()
      .then((domains) => {
        if (!cancelled) setDomainsState({ status: "loaded", domains });
      })
      .catch((err) => {
        if (!cancelled) {
          setDomainsState({
            status: "error",
            message: err instanceof Error ? err.message : String(err),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const isSubmitting = queryState.status === "loading";

  // Read via refs inside handleSubmit rather than depending on these values
  // directly. selectedDomains is a new array reference on every chip
  // toggle, so a dependency-array-based callback would get a new identity
  // on every toggle too, defeating QuestionForm's memoization. Refs let
  // handleSubmit stay referentially stable for the component's whole
  // lifetime while still reading current values at call time.
  const selectedDomainsRef = useRef(selectedDomains);
  selectedDomainsRef.current = selectedDomains;
  const isSubmittingRef = useRef(isSubmitting);
  isSubmittingRef.current = isSubmitting;

  const toggleDomain = useCallback((id: string) => {
    setSelectedDomains((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  }, []);

  // Takes the already-trimmed question as a parameter (rather than reading
  // it from state here) so this callback's identity is stable across every
  // keystroke in QuestionForm. Empty deps: identity never changes.
  const handleSubmit = useCallback(async (question: string) => {
    if (isSubmittingRef.current) return;

    const domains = selectedDomainsRef.current;
    setQueryState({ status: "loading" });
    try {
      const response = await submitQuery({
        question,
        domains: domains.length > 0 ? domains : null,
        top_k: TOP_K,
      });
      setQueryState({ status: "done", response });
    } catch (err) {
      setQueryState({
        status: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  return (
    <main className={styles.page}>
      <div className={styles.masthead}>
        <h1 className={styles.title}>Literature Review</h1>
        <p className={styles.subtitle}>
          Ask a question across the ingested scientific literature. Pick one
          or more domains to narrow the search, or leave all unselected to
          search everything.
        </p>
      </div>

      <form className={styles.console}>
        <fieldset className={styles.fieldset} disabled={isSubmitting}>
          <DomainSelector
            state={domainsState}
            selected={selectedDomains}
            onToggle={toggleDomain}
          />
          <QuestionForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
        </fieldset>
      </form>

      <section className={styles.results} aria-live="polite">
        {queryState.status === "idle" && (
          <p className={styles.emptyState}>
            Results will appear here once you ask a question.
          </p>
        )}

        {queryState.status === "loading" && (
          <div className={styles.loadingPanel}>
            <p className={styles.loadingLabel}>
              <span className={styles.loadingRail}>
                <span className={styles.loadingSweep} />
              </span>
              Searching the literature...
            </p>
          </div>
        )}

        {queryState.status === "error" && (
          <StatusPanel
            variant="error"
            title="Something went wrong"
            message={queryState.message}
          />
        )}

        {queryState.status === "done" && queryState.response.abstained && (
          <StatusPanel
            variant="abstain"
            title="No confident answer"
            message={
              queryState.response.reasoning_note ||
              "The system abstained because it did not find sufficient evidence in the corpus to answer this question."
            }
          />
        )}

        {queryState.status === "done" && !queryState.response.abstained && (
          <AnswerPanel response={queryState.response} />
        )}
      </section>
    </main>
  );
}
