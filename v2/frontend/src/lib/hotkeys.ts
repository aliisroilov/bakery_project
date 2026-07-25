import { useEffect } from "react";

/** True when the user is typing in a text field (so we don't hijack their keys). */
function inTextField(el: EventTarget | null): boolean {
  const t = el as HTMLElement | null;
  if (!t) return false;
  const tag = t.tagName;
  return tag === "TEXTAREA" || tag === "SELECT" || tag === "INPUT" || t.isContentEditable;
}

/**
 * Form/modal hotkeys:
 *   Ctrl/Cmd+Enter → save and exit
 *   Shift+Enter    → save and new (falls back to save+exit) — skipped inside a
 *                    textarea so multi-line notes still work
 *   Esc            → close (previous)
 */
export function useModalHotkeys(opts: {
  onClose?: () => void;
  onSaveExit?: () => void;
  onSaveNew?: () => void;
  canSave?: boolean;
}) {
  const { onClose, onSaveExit, onSaveNew, canSave } = opts;
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose?.();
        return;
      }
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (canSave !== false) onSaveExit?.();
        return;
      }
      if (e.key === "Enter" && e.shiftKey && !inTextField(document.activeElement)) {
        e.preventDefault();
        if (canSave !== false) (onSaveNew ?? onSaveExit)?.();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, onSaveExit, onSaveNew, canSave]);
}

/**
 * Page-level hotkeys (active only while no modal is open):
 *   Insert → create (primary "new" action)
 *   Delete → onDelete (used for "rasxod" on the kassa page)
 * Ignored while typing in a field.
 */
export function usePageHotkeys(opts: {
  onCreate?: () => void;
  onDelete?: () => void;
  disabled?: boolean;
}) {
  const { onCreate, onDelete, disabled } = opts;
  useEffect(() => {
    if (disabled) return;
    const handler = (e: KeyboardEvent) => {
      if (inTextField(document.activeElement)) return;
      if (e.key === "Insert") {
        e.preventDefault();
        onCreate?.();
      } else if (e.key === "Delete" && onDelete) {
        e.preventDefault();
        onDelete();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onCreate, onDelete, disabled]);
}
