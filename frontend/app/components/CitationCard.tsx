import { memo, type CSSProperties } from "react";
import styles from "@/app/components/CitationCard.module.css";
import ScoreMeter from "@/app/components/ScoreMeter";
import type { Citation } from "@/lib/api";

interface CitationCardProps {
  citation: Citation;
  index: number;
}

/** One citation entry: title/link, source, domain, and its relevance
 * meter. Carries the anchor id that the answer's [n] markers link to. */
function CitationCard({ citation, index }: CitationCardProps) {
  const position = index + 1;
  const staggerStyle: CSSProperties = {
    animationDelay: `${index * 40}ms`,
  };

  return (
    <div
      id={`citation-${position}`}
      className={styles.card}
      style={staggerStyle}
    >
      <span className={styles.index}>{position}</span>
      <div className={styles.body}>
        <div className={styles.head}>
          {citation.url ? (
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.title}
            >
              {citation.title}
            </a>
          ) : (
            <span className={styles.title}>{citation.title}</span>
          )}
        </div>
        <div className={styles.meta}>
          <span className={styles.domainBadge}>{citation.domain}</span>
          <span className={styles.source}>{citation.source}</span>
        </div>
        <ScoreMeter score={citation.score} />
      </div>
    </div>
  );
}

export default memo(CitationCard);
