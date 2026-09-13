/**
 * MetrCheck AI — Centralized Timezone and DateTime Utility (Frontend)
 * 
 * Standardizes parsing of UTC timestamps and conversion to India Standard Time (Asia/Kolkata).
 * Handles explicit UTC timestamps (with 'Z' / '+00:00') as well as legacy naive UTC timestamps.
 */

const IST_TIMEZONE = 'Asia/Kolkata';

/**
 * Parses a backend timestamp string into a valid JavaScript Date.
 * If the string is a legacy naive ISO string (no 'Z' or offset), it treats it as UTC.
 */
export function parseUtcDate(timestamp?: string | null): Date | null {
  if (!timestamp) return null;
  const trimmed = String(timestamp).trim();
  if (!trimmed) return null;

  // If already has timezone indicator (Z or +/-offset after time)
  let isoString = trimmed;
  if (!/[zZ]$/.test(isoString) && !/[+-]\d{2}:?\d{2}$/.test(isoString)) {
    // Legacy naive timestamp from UTC backend -> append 'Z' so JS treats as UTC
    isoString += 'Z';
  }

  const date = new Date(isoString);
  return isNaN(date.getTime()) ? null : date;
}

/**
 * Formats a timestamp into human-readable date and time in Asia/Kolkata (IST).
 * Example: "07/09/2026, 14:14:03"
 */
export function formatAnalysisDateTime(
  timestamp?: string | null,
  options?: Intl.DateTimeFormatOptions
): string {
  const date = parseUtcDate(timestamp);
  if (!date) return 'Recent analysis';

  const defaultOptions: Intl.DateTimeFormatOptions = {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    ...options,
  };

  try {
    return new Intl.DateTimeFormat('en-IN', defaultOptions).format(date);
  } catch {
    return date.toLocaleString('en-IN', { timeZone: IST_TIMEZONE });
  }
}

/**
 * Formats a timestamp into a long readable date/time (for Results page header).
 * Example: "07 September 2026, 14:14"
 */
export function formatLongDateTime(timestamp?: string | null): string {
  const date = parseUtcDate(timestamp);
  if (!date) return 'Recent analysis';

  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: IST_TIMEZONE,
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date);
  } catch {
    return date.toLocaleString('en-IN', { timeZone: IST_TIMEZONE });
  }
}

/**
 * Formats a timestamp into date-only in Asia/Kolkata (IST).
 * Example: "07/09/2026"
 */
export function formatAnalysisDate(timestamp?: string | null): string {
  const date = parseUtcDate(timestamp);
  if (!date) return 'Recent';

  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: IST_TIMEZONE,
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(date);
  } catch {
    return date.toLocaleDateString('en-IN', { timeZone: IST_TIMEZONE });
  }
}
