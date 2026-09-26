import { memo, useId, useState, type KeyboardEvent } from "react";
import styles from "@/app/components/QuestionForm.module.css";

interface QuestionFormProps {
  onSubmit: (question: string) => void;
  isSubmitting: boolean;
}

/** Natural-language question input with Enter-to-submit.
 *
 * Owns its own keystroke-level state so the parent (and its stable
 * `onSubmit` callback) never re-render on every character typed, only the
 * trimmed, submitted string bubbles up. */
function QuestionForm({ onSubmit, isSubmitting }: QuestionFormProps) {
  const [value, setValue] = useState("");
  const textareaId = useId();
  const trimmed = value.trim();
  const canSubmit = Boolean(trimmed) && !isSubmitting;

  function submit() {
    if (!canSubmit) return;
    onSubmit(trimmed);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className={styles.wrapper}>
      <label htmlFor={textareaId} className={styles.label}>
        Question
      </label>
      <textarea
        id={textareaId}
        className={styles.textarea}
        placeholder="e.g. What evidence exists for cold-chain failure rates in last-mile vaccine logistics?"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
      />
      <div className={styles.submitRow}>
        <span className={styles.submitHint}>
          Enter to search &middot; Shift+Enter for a new line
        </span>
        <button
          type="button"
          className={styles.submitButton}
          disabled={!canSubmit}
          onClick={submit}
        >
          {isSubmitting ? "Searching..." : "Search"}
        </button>
      </div>
    </div>
  );
}

export default memo(QuestionForm);
