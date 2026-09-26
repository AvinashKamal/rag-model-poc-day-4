import { memo, useId } from "react";
import styles from "@/app/components/DomainSelector.module.css";
import type { DomainsState } from "@/app/types";

interface DomainSelectorProps {
  state: DomainsState;
  selected: string[];
  onToggle: (id: string) => void;
}

/** Multi-select chip row for the enabled domains, populated entirely from
 * `GET /domains`, never a hardcoded list. */
function DomainSelector({ state, selected, onToggle }: DomainSelectorProps) {
  const labelId = useId();

  return (
    <div>
      <span id={labelId} className={styles.label}>
        Domains
      </span>

      {state.status === "loading" && (
        <div className={styles.skeletonRow}>
          <div className={styles.skeletonChip} />
          <div className={styles.skeletonChip} />
          <div className={styles.skeletonChip} />
        </div>
      )}

      {state.status === "error" && (
        <p className={styles.error}>
          Couldn&apos;t load the domain list ({state.message}). Search will
          still work across all domains.
        </p>
      )}

      {state.status === "loaded" && (
        <>
          <div
            className={styles.chipRow}
            role="group"
            aria-labelledby={labelId}
          >
            {state.domains.map((domain) => {
              const isSelected = selected.includes(domain.id);
              return (
                <button
                  key={domain.id}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => onToggle(domain.id)}
                  className={`${styles.chip} ${
                    isSelected ? styles.chipSelected : ""
                  }`}
                >
                  {domain.display_name}
                </button>
              );
            })}
          </div>
          <p className={styles.hint}>
            {selected.length === 0
              ? "No domains selected. Searching all domains."
              : `Searching ${selected.length} of ${state.domains.length} domains.`}
          </p>
        </>
      )}
    </div>
  );
}

export default memo(DomainSelector);
