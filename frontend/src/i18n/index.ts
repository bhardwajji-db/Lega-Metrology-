import en from './locales/en.json';
import hi from './locales/hi.json';
import mr from './locales/mr.json';
import bn from './locales/bn.json';
import gu from './locales/gu.json';
import pa from './locales/pa.json';
import ta from './locales/ta.json';
import te from './locales/te.json';
import kn from './locales/kn.json';
import ml from './locales/ml.json';

export type SupportedLocale = 'en' | 'hi' | 'mr' | 'bn' | 'gu' | 'pa' | 'ta' | 'te' | 'kn' | 'ml';

export const LOCALES: Record<SupportedLocale, Record<string, any>> = {
  en,
  hi,
  mr,
  bn,
  gu,
  pa,
  ta,
  te,
  kn,
  ml,
};

function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function toSnakeCase(str: string): string {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
}

function resolveProperty(obj: any, prop: string): any {
  if (!obj || typeof obj !== 'object') return undefined;
  if (prop in obj) return obj[prop];
  
  const camel = toCamelCase(prop);
  if (camel in obj) return obj[camel];
  
  const snake = toSnakeCase(prop);
  if (snake in obj) return obj[snake];

  const upper = prop.toUpperCase();
  if (upper in obj) return obj[upper];

  const lower = prop.toLowerCase();
  if (lower in obj) return obj[lower];

  return undefined;
}

function getNestedValue(obj: Record<string, any>, path: string): string | undefined {
  if (!obj) return undefined;
  const parts = path.split('.');
  let current: any = obj;
  for (const part of parts) {
    current = resolveProperty(current, part);
    if (current === undefined || current === null) {
      return undefined;
    }
  }
  return typeof current === 'string' ? current : undefined;
}

export function formatTranslation(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, key) => {
    return params[key] !== undefined ? String(params[key]) : match;
  });
}

export function translate(
  lang: string,
  key: string,
  params?: Record<string, string | number>
): string {
  const targetLocale = (LOCALES[lang as SupportedLocale] ? lang : 'en') as SupportedLocale;
  const dict = LOCALES[targetLocale];
  const fallbackDict = LOCALES.en;

  // Try target language
  let val = getNestedValue(dict, key);

  // Fallback to English
  if (val === undefined && targetLocale !== 'en') {
    val = getNestedValue(fallbackDict, key);
  }

  // Fallback to raw key if missing
  if (val === undefined) {
    val = key;
  }

  return formatTranslation(val, params);
}

export const t = translate;
