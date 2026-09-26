"use client";

import { useEffect } from "react";
import styles from "@/app/error.module.css";
import StatusPanel from "@/app/components/StatusPanel";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/** App Router error boundary for this route. Without this file, a
 * render-time throw anywhere under `app/` falls through to Next's default
 * dev overlay (or a blank screen in production) instead of the app's own
 * error UI. Reuses StatusPanel so the failure state looks like every other
 * status the app already shows, not a foreign error page. */
export default function Error({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className={styles.wrap}>
      <StatusPanel
        variant="error"
        title="Something went wrong"
        message="An unexpected error occurred while rendering this page. You can try again, or reload the page."
      />
      <button type="button" className={styles.retryButton} onClick={reset}>
        Try again
      </button>
    </main>
  );
}
