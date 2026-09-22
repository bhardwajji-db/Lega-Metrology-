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
  return cleaned.replace(/\/api\/?$/i, '').replace(/\/+$/, '');
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
      if (saved && saved.trim()) {
        const cleaned = saved.trim().replace(/\/api\/?$/i, '').replace(/\/+$/, '');
        // Ignore expired ephemeral Cloudflare tunnels so production VITE_API_URL takes precedence
        if (!cleaned.includes('trycloudflare.com')) {
          return cleaned;
        }
      }
    } catch {
      // localStorage may fail in restricted/sandboxed environments
    }
  }

  // 2. Build-time env (supports VITE_API_URL and VITE_API_BASE_URL, stripping trailing /api)
  const envRaw = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL) as string | undefined;
  if (envRaw && typeof envRaw === 'string') {
    const envUrl = envRaw.trim().replace(/\/api\/?$/i, '').replace(/\/+$/, '');
    if (envUrl) return envUrl;
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

/**
 * Whether a server URL is configured.
 * - On native mobile (Capacitor): requires an explicit host (saved or env var).
 * - On web browser: defaults to true because relative '/api' or same-origin backend is always active.
 */
export function isServerConfigured(): boolean {
  if (!isNativePlatform()) {
    return true;
  }
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
    const cleanHost = host.replace(/\/api\/?$/i, '').replace(/\/+$/, '');
    return `${cleanHost}/api`;
  }
  // If running natively in Capacitor and no host is configured, do NOT use relative '/api'
  if (isNativePlatform()) {
    return '';
  }
  // Web browser fallback: Vite dev proxy or Nginx reverse proxy handles relative '/api'
  return '/api';
}

/** Resolve an asset path (e.g. /uploads/foo.jpg or /api/images/foo.jpg) to an authenticated absolute URL. */
export function getAssetUrl(path: string): string {
  if (!path) return '';
  if (path.startsWith('data:')) return path;
  let cleanUrl = path.startsWith('/uploads/') ? path.replace('/uploads/', '/api/images/') : path;
  const host = getApiHost();
  let fullUrl = (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://'))
    ? cleanUrl
    : (host ? `${host}${cleanUrl}` : cleanUrl);
  try {
    const token = localStorage.getItem('metrcheck-token');
    if (token && !fullUrl.includes('token=')) {
      const sep = fullUrl.includes('?') ? '&' : '?';
      fullUrl = `${fullUrl}${sep}token=${encodeURIComponent(token)}`;
    }
  } catch {}
  return fullUrl;
}

// ---------------------------------------------------------------------------
// Connectivity & Health tests
// ---------------------------------------------------------------------------

export interface ServerTestResult {
  ok: boolean;
  status?: 'operational' | 'degraded' | 'offline';
  services?: {
    backend: string;
    database: string;
    ocr: string;
  };
  data?: any;
  error?: string;
}

/** Check system health against the active server configuration (handles web auto-proxy and custom hosts). */
export async function checkSystemHealth(): Promise<ServerTestResult> {
  const host = getApiHost();
  const isWeb = typeof window !== 'undefined' && !isNativePlatform();

  // If on native mobile and no server is configured
  if (isNativePlatform() && !host) {
    return {
      ok: false,
      status: 'offline',
      error: 'No server URL configured for native mobile app.'
    };
  }

  // On web without an explicit host override, test relative /api/health
  const targetEndpoint = host ? `${host}/api/health` : (isWeb ? '/api/health' : '');
  if (!targetEndpoint) {
    return { ok: false, status: 'offline', error: 'No active server endpoint.' };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    const res = await fetch(targetEndpoint, {
      method: 'GET',
      headers: { 'Accept': 'application/json', 'ngrok-skip-browser-warning': 'true' },
      signal: controller.signal,
    });
    clearTimeout(timeout);

    const contentType = res.headers.get('content-type') || '';
    const text = await res.text();

    const isHtml = text.trim().toLowerCase().startsWith('<!doctype') || text.trim().toLowerCase().startsWith('<html') || text.trim().startsWith('<');
    const isJson = contentType.toLowerCase().includes('application/json');

    if (isHtml || (!isJson && !text.trim().startsWith('{'))) {
      return {
        ok: false,
        status: 'offline',
        error: `Server responded with HTML instead of JSON API response. Check that target is FastAPI (port 8000).`
      };
    }

    const data = JSON.parse(text);
    if (!res.ok) {
      return {
        ok: false,
        status: 'offline',
        error: data?.detail || `Server returned error (${res.status} ${res.statusText})`
      };
    }

    const sysStatus = data.status === 'operational' || data.status === 'healthy' ? 'operational' : (data.status === 'degraded' ? 'degraded' : 'offline');
    return {
      ok: true,
      status: sysStatus,
      services: data.services || {
        backend: 'operational',
        database: data.database === 'connected' ? 'operational' : 'unavailable',
        ocr: data.ocr_available ? 'operational' : 'degraded',
      },
      data
    };
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return { ok: false, status: 'offline', error: 'Unable to connect to the MetrCheck server (connection timed out).' };
    }
    return {
      ok: false,
      status: 'offline',
      error: `Unable to connect to the MetrCheck server (${err.message || 'connection failed'}).`
    };
  }
}

/** Hit /api/health on a user-specified server URL and report back. Safely validates Content-Type and URL structure. */
export async function testServerConnection(serverUrl: string): Promise<ServerTestResult> {
  const isWeb = typeof window !== 'undefined' && !isNativePlatform();
  const trimmed = (serverUrl || '').trim();

  // If testing empty on web, test default auto-proxy
  if (!trimmed && isWeb) {
    return checkSystemHealth();
  }

  const normalized = normalizeServerUrl(trimmed);
  if (!normalized) {
    return { ok: false, error: 'Please enter a valid server URL starting with http:// or https://' };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    const res = await fetch(`${normalized}/api/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json', 'ngrok-skip-browser-warning': 'true' },
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

    const sysStatus = data.status === 'operational' || data.status === 'healthy' ? 'operational' : (data.status === 'degraded' ? 'degraded' : 'offline');
    return {
      ok: true,
      status: sysStatus,
      services: data.services || {
        backend: 'operational',
        database: data.database === 'connected' ? 'operational' : 'unavailable',
        ocr: data.ocr_available ? 'operational' : 'degraded',
      },
      data
    };
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return { ok: false, error: 'Unable to connect to the MetrCheck server (connection timed out after 6 seconds).' };
    }
    return {
      ok: false,
      error: `Unable to connect to the MetrCheck server (${err.message || 'connection failed'}). Check the URL, network connection, and firewall.`
    };
  }
}
