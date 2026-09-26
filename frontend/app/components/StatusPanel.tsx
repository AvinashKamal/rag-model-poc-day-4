import { memo } from "react";
import styles from "@/app/components/StatusPanel.module.css";

interface StatusPanelProps {
  variant: "error" | "abstain";
  title: string;
  message: string;
}

/** Shared shell for the error and abstained result states: same anatomy,
 * different tone, so the two states stay visually distinct at a glance. */
function StatusPanel({ variant, title, message }: StatusPanelProps) {
  const variantClass = variant === "error" ? styles.error : styles.abstain;

  return (
    <div className={`${styles.panel} ${variantClass}`}>
      <span className={styles.icon} aria-hidden="true">
        {variant === "error" ? "!" : "?"}
      </span>
      <div className={styles.body}>
        <p className={styles.title}>{title}</p>
        <p className={styles.message}>{message}</p>
      </div>
    </div>
  );
}

export default memo(StatusPanel);
