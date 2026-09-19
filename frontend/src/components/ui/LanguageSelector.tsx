import React, { useState, useRef, useEffect } from 'react';
import { Globe, ChevronDown, Check } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface LanguageSelectorProps {
  compact?: boolean;
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({ compact = true }) => {
  const { selectedLanguage, setLanguage, currentLanguage, supportedLanguages } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-50 dark:bg-slate-800/90 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
        aria-label="Select report language"
        aria-expanded={isOpen}
        title="Select Report Output Language"
      >
        <Globe className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />
        <span className={compact ? 'hidden sm:inline font-semibold' : 'font-semibold'}>
          {currentLanguage.native}
        </span>
        <span className={compact ? 'sm:hidden font-semibold' : 'hidden'}>
          {currentLanguage.code.toUpperCase()}
        </span>
        <ChevronDown className={`w-3 h-3 text-slate-400 dark:text-slate-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/5 dark:bg-black/20"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-60 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 shadow-2xl p-2 z-50 ring-1 ring-black/5 animate-in fade-in duration-150">
            <div className="px-3 py-1.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider flex items-center gap-1">
                <Globe className="w-3 h-3 text-indigo-500" />
                Report Language
              </span>
              <span className="text-[9px] bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 font-bold px-1.5 py-0.5 rounded">
                10 Languages
              </span>
            </div>

            <div className="py-1 max-h-72 overflow-y-auto space-y-0.5">
              {supportedLanguages.map((lang) => {
                const isSelected = selectedLanguage === lang.code;
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => {
                      setLanguage(lang.code);
                      setIsOpen(false);
                    }}
                    className={`w-full text-left px-3 py-1.5 rounded-xl text-xs transition flex items-center justify-between cursor-pointer ${
                      isSelected
                        ? 'bg-indigo-50 dark:bg-indigo-950/70 text-indigo-950 dark:text-indigo-200 font-bold border border-indigo-200/60 dark:border-indigo-800/60'
                        : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium">{lang.native}</span>
                      <span className="text-[11px] text-slate-400 dark:text-slate-500">
                        ({lang.label})
                      </span>
                    </div>
                    {isSelected && <Check className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default LanguageSelector;
