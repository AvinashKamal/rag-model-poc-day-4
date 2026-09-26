import { memo, useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import styles from "@/app/components/AnswerPanel.module.css";
import CitationCard from "@/app/components/CitationCard";
import type { QueryResponse } from "@/lib/api";

interface AnswerPanelProps {
  response: QueryResponse;
}

/** Rewrites in-range `[n]` citation markers into markdown links pointing
 * at the matching citation anchor, before the string reaches ReactMarkdown.
 * Out-of-range/malformed markers are left as plain text. */
function injectCitationLinks(answer: string, citationCount: number): string {
  return answer.replace(/\[(\d+)\]/g, (marker, numStr: string) => {
    const n = Number(numStr);
    if (n >= 1 && n <= citationCount) {
      return `[${marker}](#citation-${n})`;
    }
    return marker;
  });
}

// The answer is model output derived from untrusted retrieved literature,
// so it must never be able to introduce a clickable destination of its
// own (e.g. an out-of-range `[99](https://evil.example)` marker slipped
// into the text). The only links this component ever renders are the
// same-page citation anchors it generates itself in injectCitationLinks;
// every other href, however it got into the markdown, renders as inert
// text. The citation sidebar (CitationCard) is the sole source of real,
// backend-provided external links.
function AnswerLink({
  href,
  children,
}: React.ComponentPropsWithoutRef<"a">) {
  const isCitation = href?.startsWith("#citation-") ?? false;

  if (isCitation) {
    return (
      <a href={href} className={styles.citationMarker}>
        {children}
      </a>
    );
  }

  return <>{children}</>;
}

// react-markdown renders a plain `<img src>` from markdown image syntax,
// and the browser fetches that src immediately on render, no click
// required. Since the answer is untrusted model output, that would let
// retrieved literature content trigger an arbitrary outbound request (or
// worse, a tracking pixel) just by us rendering the answer. Neutralize it
// the same way AnswerLink neutralizes non-citation links: render the
// alt text only, never the underlying src.
function AnswerImage({ alt }: React.ComponentPropsWithoutRef<"img">) {
  if (!alt) return null;
  return <span className={styles.imageAlt}>{alt}</span>;
}

// Plain markdown-to-React rendering only, no rehype-raw, no
// dangerouslySetInnerHTML. The answer is model output derived from
// untrusted retrieved literature, so raw HTML in it must never execute;
// react-markdown's default (no raw-HTML plugin) already guarantees that.
const markdownComponents: Components = {
  a: AnswerLink,
  img: AnswerImage,
};

function AnswerPanel({ response }: AnswerPanelProps) {
  const processedAnswer = useMemo(() => {
    if (!response.answer) return null;
    return injectCitationLinks(response.answer, response.citations.length);
  }, [response.answer, response.citations.length]);

  return (
    <div className={styles.layout}>
      <div className={styles.answerCard}>
        <p className={styles.label}>Answer</p>
        <div className={styles.answerText}>
          {processedAnswer ? (
            <ReactMarkdown components={markdownComponents}>
              {processedAnswer}
            </ReactMarkdown>
          ) : (
            "The backend returned no answer text."
          )}
        </div>
        {response.reasoning_note && (
          <p className={styles.reasoningNote}>{response.reasoning_note}</p>
        )}
      </div>

      <div className={styles.citationList}>
        <p className={styles.label}>Citations ({response.citations.length})</p>
        {response.citations.length === 0 && (
          <p className={styles.noCitations}>No citations returned.</p>
        )}
        {response.citations.map((citation, i) => (
          <CitationCard key={i} citation={citation} index={i} />
        ))}
      </div>
    </div>
  );
}

export default memo(AnswerPanel);
