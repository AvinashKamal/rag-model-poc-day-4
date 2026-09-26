import { memo } from "react";
import styles from "@/app/components/ScoreMeter.module.css";

interface ScoreMeterProps {
  score: number;
}

const BUCKETS = [
  { max: 0.2, className: "fill1" },
  { max: 0.4, className: "fill2" },
  { max: 0.6, className: "fill3" },
  { max: 0.8, className: "fill4" },
  { max: Infinity, className: "fill5" },
] as const;

/**
 * Relevance-score meter for a single citation.
 *
 * Dataviz-skill framing: this is one scalar per citation, not a chart, so
 * it's a compact meter (sequential single-hue fill and a lighter track of
 * the same ramp), not a plotted series. The numeric value rides alongside
 * in a text token (never the fill color), and the fill width doubles the
 * magnitude encoding so the bar is legible even without the number.
 */
function ScoreMeter({ score }: ScoreMeterProps) {
  const clamped = Number.isFinite(score) ? Math.min(1, Math.max(0, score)) : 0;
  const percent = Math.round(clamped * 100);
  const bucket = BUCKETS.find((b) => clamped <= b.max) ?? BUCKETS[BUCKETS.length - 1];

  return (
    <div
      className={styles.meter}
      role="img"
      aria-label={`Relevance score: ${percent}%`}
    >
      <div className={styles.track}>
        <div
          className={`${styles.fill} ${styles[bucket.className]}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className={styles.value}>{percent}%</span>
    </div>
  );
}

export default memo(ScoreMeter);
