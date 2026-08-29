import { useEffect, useState } from "react";

type BottomSheetProps = {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
};

/**
 * TikTok-comments-style bottom sheet: slides up from the bottom edge with a
 * drag handle, dims the backdrop and fills the width on phones. Used for the
 * mobile "More" menu instead of a centered card so it feels native.
 */
const BottomSheet = ({ isOpen, onClose, title, children }: BottomSheetProps) => {
  const [rendered, setRendered] = useState(isOpen);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setRendered(true);
      // Next frame starts the slide-up transition (transition-transform).
      const raf = requestAnimationFrame(() => setShow(true));
      return () => cancelAnimationFrame(raf);
    }
    setShow(false);
    const timer = setTimeout(() => setRendered(false), 260);
    return () => clearTimeout(timer);
  }, [isOpen]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, [isOpen, onClose]);

  if (!rendered) return null;

  return (
    <div className="fixed inset-0 z-50" aria-hidden={!show}>
      <div
        className={`absolute inset-0 bg-black/50 transition-opacity duration-300 ${
          show ? "opacity-100" : "opacity-0"
        }`}
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-label={title}
        className={`absolute inset-x-0 bottom-0 z-10 mx-auto w-full max-w-lg rounded-t-3xl bg-white shadow-2xl transition-transform duration-300 ease-out dark:bg-slate-900 ${
          show ? "translate-y-0" : "translate-y-full"
        }`}
      >
        {/* Drag handle */}
        <div className="mx-auto mt-2 h-1.5 w-10 rounded-full bg-slate-300 dark:bg-slate-700" />
        <div className="flex items-center justify-between px-5 pt-3">
          {title && <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h2>}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="max-h-[72vh] overflow-y-auto px-5 pb-8 pt-4">{children}</div>
      </div>
    </div>
  );
};

export default BottomSheet;