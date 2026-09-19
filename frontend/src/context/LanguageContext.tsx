import { createContext, useContext, useEffect, useState, useMemo, useCallback, type ReactNode } from 'react';
import { type SupportedReportLanguage, SUPPORTED_REPORT_LANGUAGES } from '../types';
import { translate } from '../i18n';

export const LANGUAGE_STORAGE_KEY = 'metrcheck_report_language';

interface LanguageContextType {
  selectedLanguage: string;
  setLanguage: (langCode: string) => void;
  currentLanguage: SupportedReportLanguage;
  supportedLanguages: SupportedReportLanguage[];
  t: (key: string, params?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [selectedLanguage, setSelectedLanguageState] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(LANGUAGE_STORAGE_KEY);
      if (saved && SUPPORTED_REPORT_LANGUAGES.some(l => l.code === saved)) {
        return saved;
      }
    } catch {
      // Fallback
    }
    return 'en';
  });

  const setLanguage = (langCode: string) => {
    const valid = SUPPORTED_REPORT_LANGUAGES.some(l => l.code === langCode);
    const target = valid ? langCode : 'en';
    setSelectedLanguageState(target);
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, target);
    } catch {
      // Ignore
    }
  };

  useEffect(() => {
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, selectedLanguage);
    } catch {
      // Ignore
    }
  }, [selectedLanguage]);

  const currentLanguage = useMemo(() => {
    return SUPPORTED_REPORT_LANGUAGES.find(l => l.code === selectedLanguage) || SUPPORTED_REPORT_LANGUAGES[0];
  }, [selectedLanguage]);

  const t = useCallback((key: string, params?: Record<string, string | number>) => {
    return translate(selectedLanguage, key, params);
  }, [selectedLanguage]);

  return (
    <LanguageContext.Provider
      value={{
        selectedLanguage,
        setLanguage,
        currentLanguage,
        supportedLanguages: SUPPORTED_REPORT_LANGUAGES,
        t,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
