import { Capacitor } from '@capacitor/core';

/**
 * MetrCheck AI — Centralized API Configuration
 *
 * URL resolution priority:
 *   1. User-saved server URL in localStorage (explicit user override)
 *   2. VITE_API_URL build-time env var
 *   3. Empty string → ServerSetup screen on Capacitor / manual entry on web
 */

const STORAGE_KEY = 'metrcheck_api_url';

// ---------------------------------------------------------------------------
// Platform helpers
// ---------------------------------------------------------------------------

/** Whether the app is running as a native mobile app (Capacitor Android / iOS). */
export function isNativePlatform(): boolean {
  try {
    return Capacitor.isNativePlatform();
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// URL helpers
// ---------------------------------------------------------------------------

/** Normalize a server URL: trim, strip trailing slashes, basic validation. */
export function normalizeServerUrl(url: string): string | null {
  const cleaned = (url || '').trim().replace(/\/+$/, '');
  if (!cleaned) return null;
  if (!/^https?:\/\/.+/i.test(cleaned)) return null;
  try {
    new URL(cleaned);
  } catch {
    return null;
  }
  return cleaned;
}

// ---------------------------------------------------------------------------
// Host get / set
// ---------------------------------------------------------------------------

/**
 * Get the configured API host URL.
 *
 * Priority:
 *   1. Saved server URL in localStorage (user-configured, explicit override)
 *   2. VITE_API_URL environment variable (set at build time)
 *   3. '' (empty — no server configured)
 */
export function getApiHost(): string {
  // 1. Persisted user choice (takes precedence so users can reconfigure server in-app)
  if (typeof window !== 'undefined') {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && saved.trim()) return saved.trim().replace(/\/+$/, '');
    } catch {
      // localStorage may fail in restricted/sandboxed environments
    }
  }

  // 2. Build-time env
  if (import.meta.env.VITE_API_URL && typeof import.meta.env.VITE_API_URL === 'string') {
    const envUrl = import.meta.env.VITE_API_URL.trim();
    if (envUrl) return envUrl.replace(/\/+$/, '');
  }

  // 3. Not configured
  return '';
}

/** Persist (or clear) the user-chosen API host. */
export function setApiHost(url: string): void {
  if (typeof window === 'undefined') return;
  const normalized = normalizeServerUrl(url);
  if (normalized) {
    try {
      localStorage.setItem(STORAGE_KEY, normalized);
    } catch {
      // ignore storage quota issues
    }
  } else {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }
}

/** Whether a server URL is configured (via env OR localStorage). */
export function isServerConfigured(): boolean {
  return getApiHost() !== '';
}

// ---------------------------------------------------------------------------
// Derived URLs
// ---------------------------------------------------------------------------

/**
 * Full API base URL = host + /api.
 *
 * CRITICAL CAPACITOR / MOBILE RULE:
 * - On web (browser): Falls back to '/api' for Vite dev proxy or reverse-proxy.
 * - On native mobile (Android APK / Capacitor): NEVER fall back to relative '/api'!
 *   Relative '/api' inside a native WebView resolves to `https://localhost/api`
 *   (the frontend origin), which is caught by Capacitor's WebView asset loader
 *   and falls through to `index.html` (HTML beginning with `<!doctype html>`).
 *   Returning '' signals to the API client that no backend is configured.
 */
export function getApiBaseUrl(): string {
  const host = getApiHost();
  if (host) {
    return `${host}/api`;
  }
  // If running natively in Capacitor and no host is configured, do NOT use relative '/api'
  if (isNativePlatform()) {
    return '';
  }
  // Web browser fallback: Vite dev proxy or Nginx reverse proxy handles relative '/api'
  return '/api';
}

/** Resolve a relative asset path (e.g. /uploads/foo.jpg) to an absolute URL. */
export function getAssetUrl(path: string): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('data:')) return path;
  const host = getApiHost();
  return host ? `${host}${path}` : path;
}

// ---------------------------------------------------------------------------
// Connectivity test
// ---------------------------------------------------------------------------

export interface ServerTestResult {
  ok: boolean;
  data?: any;
  error?: string;
}

/** Hit /api/health on the given server URL and report back. Safely validates Content-Type. */
export async function testServerConnection(serverUrl: string): Promise<ServerTestResult> {
  const normalized = normalizeServerUrl(serverUrl);
  if (!normalized) {
    return { ok: false, error: 'Invalid server URL. Must start with http:// or https://' };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(`${normalized}/api/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: controller.signal,
    });
    clearTimeout(timeout);

    const contentType = res.headers.get('content-type') || '';
    const text = await res.text();

    // Verify response is actually JSON and not an HTML fallback page
    const isHtml = text.trim().toLowerCase().startsWith('<!doctype') || text.trim().toLowerCase().startsWith('<html') || text.trim().startsWith('<');
    const isJson = contentType.toLowerCase().includes('application/json');

    if (isHtml || (!isJson && !text.trim().startsWith('{'))) {
      return {
        ok: false,
        error: `Connected to server (${res.status} ${res.statusText}), but received HTML web page instead of JSON API response. Verify that the URL points to FastAPI (port 8000), not the web frontend.`
      };
    }

    let data: any = null;
    try {
      data = JSON.parse(text);
    } catch {
      return { ok: false, error: 'Connected to server, but response could not be parsed as valid JSON.' };
    }

    if (!res.ok) {
      return { ok: false, error: data?.detail || `Server returned error (${res.status} ${res.statusText})` };
    }

    return { ok: true, data };
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return { ok: false, error: 'Connection timed out (8 s). The server may be unreachable.' };
    }
    return {
      ok: false,
      error: `Server unreachable (${err.message || 'connection failed'}). Check the URL, network connection, and firewall.`
    };
  }
}
