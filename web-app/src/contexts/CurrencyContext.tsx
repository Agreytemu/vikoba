// Currency context: location-based detection, graceful fallback, manual picker.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import Modal from "@/components/ui/Modal";
import {
  DEFAULT_CURRENCY,
  currencyOptions,
  detectCurrency,
  formatCurrency,
  type CurrencySource,
  type CurrencyState,
} from "@/lib/currency";

const STORAGE_KEY = "vikoba_currency_v1";

interface StoredCurrency extends CurrencyState {
  ts: number;
}

type PromptState = "none" | "ask" | "detecting" | "note";

interface CurrencyContextValue {
  currency: string;
  countryCode: string;
  countryName: string;
  source: CurrencySource;
  promptState: PromptState;
  formatMoney: (amount: number, options?: { maxFractionDigits?: number }) => string;
  requestDetection: () => void;
  dismissPrompt: () => void;
  setCurrencyManual: (code: string) => void;
  openPicker: () => void;
  closePicker: () => void;
  pickerOpen: boolean;
}

const CurrencyContext = createContext<CurrencyContextValue | null>(null);

function loadStored(): StoredCurrency | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredCurrency;
    if (!parsed || typeof parsed.currency !== "string") return null;
    return parsed;
  } catch {
    return null;
  }
}

function store(state: CurrencyState, source: CurrencySource) {
  const payload: StoredCurrency = { ...state, source, ts: Date.now() };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // storage unavailable (private mode) — detection still works in-memory
  }
}

async function getGeoPermission(): Promise<string | null> {
  try {
    if (!navigator.permissions?.query) return null;
    const result = await navigator.permissions.query({
      name: "geolocation",
    } as PermissionDescriptor);
    return result.state; // "granted" | "prompt" | "denied" | "unknown"
  } catch {
    return null;
  }
}

function defaultState(): CurrencyState {
  const stored = loadStored();
  return {
    currency: stored?.currency || DEFAULT_CURRENCY,
    countryCode: stored?.countryCode || "",
    countryName: stored?.countryName || "",
    source: (stored?.source || "default") as CurrencySource,
  };
}

export const CurrencyProvider = ({ children }: { children: ReactNode }) => {
  const { i18n } = useTranslation();
  const [state, setState] = useState<CurrencyState>(defaultState);
  const [currency, setCurrency] = useState(() =>
    loadStored()?.currency || DEFAULT_CURRENCY,
  );
  const [promptState, setPromptState] = useState<PromptState>("none");
  const [pickerOpen, setPickerOpen] = useState(false);
  const ranDetection = useRef(false);

  const formatMoney = useCallback(
    (amount: number, options?: { maxFractionDigits?: number }) =>
      formatCurrency(amount, currency, i18n.language, options),
    [currency, i18n.language],
  );

  const applyDetection = useCallback(async () => {
    const result = await detectCurrency();
    setState(result);
    setCurrency(result.currency);
    store(result, result.source);
    setPromptState("note");
  }, []);

  const requestDetection = useCallback(() => {
    if (ranDetection.current) return;
    ranDetection.current = true;
    setPromptState("detecting");
    void applyDetection();
  }, [applyDetection]);

  const dismissPrompt = useCallback(() => {
    store(
      { currency: DEFAULT_CURRENCY, countryCode: "", countryName: "", source: "default" },
      "default",
    );
    setPromptState("note");
  }, []);

  const setCurrencyManual = useCallback(
    (code: string) => {
      const next: CurrencyState = {
        currency: code,
        countryCode: "",
        countryName: "",
        source: "manual",
      };
      setState(next);
      setCurrency(code);
      store(next, "manual");
      setPromptState("note");
      setPickerOpen(false);
    },
    [],
  );

  // Kick off detection only once, when the app shell mounts: if the browser
  // already granted permission we detect silently; if it needs the prompt we
  // surface the friendly Dashboard card; if it is denied we fall back to IP.
  useEffect(() => {
    if (ranDetection.current) return;
    if (loadStored()) return;
    let cancelled = false;
    void (async () => {
      const permission = await getGeoPermission();
      if (cancelled) return;
      if (permission === "granted") {
        ranDetection.current = true;
        setPromptState("detecting");
        void applyDetection();
      } else if (permission === "denied") {
        ranDetection.current = true;
        setPromptState("detecting");
        const result = await detectCurrency();
        if (!cancelled) {
          setState(result);
          setCurrency(result.currency);
          store(result, result.source);
          setPromptState("note");
        }
      } else {
        setPromptState("ask");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<CurrencyContextValue>(
    () => ({
      currency: state.currency,
      countryCode: state.countryCode,
      countryName: state.countryName,
      source: state.source,
      promptState,
      formatMoney,
      requestDetection,
      dismissPrompt,
      setCurrencyManual,
      openPicker: () => setPickerOpen(true),
      closePicker: () => setPickerOpen(false),
      pickerOpen,
    }),
    [state, promptState, formatMoney, requestDetection, dismissPrompt, setCurrencyManual, pickerOpen],
  );

  return (
    <CurrencyContext.Provider value={value}>
      {children}
      <Modal
        isOpen={pickerOpen}
        onClose={() => setPickerOpen(false)}
        title="Choose currency"
      >
        <div className="grid max-h-[60vh] grid-cols-2 gap-2 overflow-y-auto sm:grid-cols-3">
          {currencyOptions.map((option) => (
            <button
              key={option.code}
              type="button"
              onClick={() => setCurrencyManual(option.code)}
              className={`flex flex-col items-start rounded-xl border px-3 py-3 text-left transition ${
                option.code === state.currency
                  ? "border-blue-600 bg-blue-50 dark:bg-blue-950/40"
                  : "border-slate-200 hover:border-blue-300 dark:border-slate-800"
              }`}
            >
              <span className="font-semibold">{option.code}</span>
              <span className="text-xs text-slate-500">{option.country}</span>
            </button>
          ))}
        </div>
      </Modal>
    </CurrencyContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useCurrency = (): CurrencyContextValue => {
  const context = useContext(CurrencyContext);
  if (!context) {
    throw new Error("useCurrency must be used inside <CurrencyProvider>");
  }
  return context;
};