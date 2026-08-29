import { useTranslation } from "react-i18next";
import { supportedLanguages } from "@/i18n/config";

const LanguageSwitcher = () => {
  const { t, i18n } = useTranslation();

  return (
    <label className="flex items-center gap-x-2 text-sm">
      <span className="sr-only">{t("language.label")}</span>
      <select
        aria-label={t("language.label")}
        value={i18n.resolvedLanguage}
        onChange={(e) => i18n.changeLanguage(e.target.value)}
        className="rounded-md border border-white/40 bg-transparent px-2 py-1 text-white focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
      >
        {supportedLanguages.map((lang) => (
          <option key={lang.code} value={lang.code} className="text-slate-900">
            {lang.label}
          </option>
        ))}
      </select>
    </label>
  );
};

export default LanguageSwitcher;
