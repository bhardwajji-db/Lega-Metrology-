import { type AnalysisResponse, type DashboardStats, type HistoryItem, type ComplianceRule, type AuthUser, type TrendPoint, type StatusBreakdown, type PenaltyEstimate, type ShowCauseNotice, type ProductInfo, type ComplianceResult } from '../types';
import { getApiHost, setApiHost, getApiBaseUrl, getAssetUrl, isNativePlatform } from '../config/api';

// Re-export so existing imports from 'services/api' keep working
export { getApiHost, setApiHost, getApiBaseUrl, getAssetUrl, isNativePlatform };

const BASE_URL = {
  valueOf: () => getApiBaseUrl(),
  toString: () => getApiBaseUrl()
};

const TOKEN_KEY = 'metrcheck-token';

export const tokenStore = {
  get: (): string | null => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (token: string) => {
    try { localStorage.setItem(TOKEN_KEY, token); } catch { /* ignore */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  },
};

function authHeaders(): Record<string, string> {
  const token = tokenStore.get();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJSON<T>(url: string, options?: RequestInit & { _timeout?: number }): Promise<T> {
  const isAuthOrCritical = url.includes('/auth/') || url.includes('/analyze');
  const headers: Record<string, string> = {
    'Accept': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
    ...authHeaders(),
  };

  // Prevent ANY relative fallback on native mobile APK when no host is configured.
  // Relative URLs (e.g. '/api/...', '/auth/login') resolve to the WebView's own
  // origin (https://localhost) and return index.html — not JSON.
  if (!url || (url.startsWith('/') && isNativePlatform() && !getApiHost())) {
    const errorMsg = 'No backend server configured. Please configure your MetrCheck AI server address in Server Settings.';
    console.error(`[MetrCheck API] Blocked relative request without configured host on mobile: ${url}`);
    throw new Error(errorMsg);
  }

  const timeoutMs = options?._timeout ?? 30000;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  // Safe request logging (URL and method only — never credentials or payload)
  if (isAuthOrCritical) {
    console.log(`[MetrCheck API] Request: ${options?.method || 'GET'} ${url}`);
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers, signal: controller.signal });
  } catch (err: any) {
    clearTimeout(timeout);
    if (err.name === 'AbortError') {
      if (isAuthOrCritical) console.error(`[MetrCheck API] Request timed out (${timeoutMs}ms) for ${url}`);
      throw new Error('Request timed out. The backend server may be busy or unreachable.');
    }
    const host = getApiHost();
    const hostDesc = host ? `(${host})` : '(No server configured)';
    if (isAuthOrCritical) {
      console.error(`[MetrCheck API] Network connection failed for ${url}:`, err.message);
    }
    if (!host && isNativePlatform()) {
      throw new Error('No backend server configured. Please tap "Server Settings" on the login screen to set your server URL.');
    }
    throw new Error(
      `Cannot connect to backend server ${hostDesc}. Please verify that the FastAPI server is running (port 8000) and your device is on the same network.`
    );
  } finally {
    clearTimeout(timeout);
  }

  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();

  // Safe response debug logging (status, content-type, sanitized preview)
  if (isAuthOrCritical) {
    const preview = text.length > 120 ? text.substring(0, 120).replace(/\r?\n|\r/g, ' ') + '…' : text.replace(/\r?\n|\r/g, ' ');
    const sanitizedPreview = preview
      .replace(/"token"\s*:\s*"[^"]+"/g, '"token":"[REDACTED]"')
      .replace(/"password"\s*:\s*"[^"]+"/g, '"password":"[REDACTED]"');
    console.log(`[MetrCheck API] Status: ${response.status} ${response.statusText}`);
    console.log(`[MetrCheck API] Content-Type: ${contentType || '[NONE]'}`);
    console.log(`[MetrCheck API] Body Preview: ${sanitizedPreview}`);
  }

  const isJsonHeader = contentType.toLowerCase().includes('application/json');
  const isHtml = text.trim().toLowerCase().startsWith('<!doctype') || text.trim().toLowerCase().startsWith('<html') || text.trim().startsWith('<');

  let data: any = null;
  // NEVER blindly call response.json() if Content-Type is not application/json or if body is HTML
  if (isJsonHeader || (!isHtml && (text.trim().startsWith('{') || text.trim().startsWith('[')))) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  // Handle HTML document fallback (e.g. Capacitor WebView routing to index.html instead of FastAPI)
  if (isHtml || (!isJsonHeader && data === null)) {
    const host = getApiHost();
    console.error(`[MetrCheck API] Expected JSON from ${url}, but received non-JSON (${contentType || 'unknown'}). Status: ${response.status}`);
    if (isHtml) {
      throw new Error(
        `Backend/API unavailable: Server returned an HTML web page instead of JSON (${response.status} ${response.statusText}). ` +
        `Current server URL: "${host || 'none'}". Verify that the URL points to the FastAPI backend (e.g. port 8000), NOT the web frontend.`
      );
    }
    throw new Error(
      `Backend/API unavailable: Server returned unexpected content-type "${contentType || 'unknown'}" (${response.status} ${response.statusText}).`
    );
  }

  if (!response.ok) {
    const detail = data?.detail || (text.startsWith('<') ? `Server error (${response.status}). Check your server connection.` : text);
    if (response.status === 401) {
      if (!url.includes('/auth/login')) {
        tokenStore.clear();
      }
      throw new Error(detail || 'Session expired. Please log in again.');
    }
    if (response.status === 403) {
      throw new Error(detail || 'Access denied. You do not have permission for this action.');
    }
    if (response.status === 404) {
      throw new Error(detail || 'Resource not found. Please verify the API endpoint.');
    }
    if (response.status === 422) {
      throw new Error(detail || 'Invalid request. Please check your input.');
    }
    if (response.status === 429) {
      throw new Error(detail || 'Too many requests. Please wait a moment and try again.');
    }
    if (response.status >= 500) {
      throw new Error(detail || 'Server error. Please try again later.');
    }
    throw new Error(detail || `Request failed (${response.status}).`);
  }

  if (data === null) {
    throw new Error(
      'Received unexpected response from server. Please verify the Server URL in Settings.'
    );
  }

  return data as T;
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────
  login: (username: string, password: string): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),

  forgotPassword: (identifier: string): Promise<{ message: string; dev_token?: string }> =>
    fetchJSON<{ message: string; dev_token?: string }>(`${BASE_URL}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier }),
    }),

  verifyResetToken: (token: string): Promise<{ valid: boolean; username?: string }> =>
    fetchJSON<{ valid: boolean; username?: string }>(`${BASE_URL}/auth/verify-reset-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  resetPassword: (token: string, new_password: string): Promise<{ message: string }> =>
    fetchJSON<{ message: string }>(`${BASE_URL}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password }),
    }),

  verifyInvitation: (token: string): Promise<import('../types').InvitationVerification> =>
    fetchJSON<import('../types').InvitationVerification>(`${BASE_URL}/auth/verify-invitation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  activateAccount: (token: string, password: string): Promise<{ message: string; username: string }> =>
    fetchJSON<{ message: string; username: string }>(`${BASE_URL}/auth/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    }),

  register: (body: { username: string; email: string; password: string; full_name?: string; role?: string }): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  getMe: (): Promise<AuthUser> => fetchJSON<AuthUser>(`${BASE_URL}/auth/me`),

  updateMyEmail: (email: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/me/email`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }),

  // ── Administration API (/api/admin) ──────────────────────────────────
  adminGetUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/admin/users`),

  adminProvisionUser: (body: {
    full_name?: string;
    username: string;
    email: string;
    role: string;
    jurisdiction?: string;
  }): Promise<{ message: string; user: AuthUser; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; user: AuthUser; dev_invitation_token?: string }>(`${BASE_URL}/admin/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  adminResendInvitation: (username: string): Promise<{ message: string; username: string; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; username: string; dev_invitation_token?: string }>(
      `${BASE_URL}/admin/users/${encodeURIComponent(username)}/resend-invitation`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    ),

  adminSuspendUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/suspend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminReactivateUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/reactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminChangeRole: (username: string, role: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/change-role`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    }),

  adminDeleteUser: (username: string): Promise<void> =>
    fetchJSON<void>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
    }),

  adminGetAuditLogs: (limit = 50): Promise<import('../types').AccountAuditLog[]> =>
    fetchJSON<import('../types').AccountAuditLog[]>(`${BASE_URL}/admin/audit-logs?limit=${limit}`),

  // Legacy User APIs
  getUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/auth/users`),

  createUser: (body: { username: string; email?: string; password: string; full_name?: string; jurisdiction?: string; role?: string }): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateUser: (
    username: string,
    updates: { full_name?: string; jurisdiction?: string; email?: string; role?: string; new_password?: string }
  ): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    }),

  deleteUser: (username: string): Promise<void> =>
    fetchJSON<void>(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
    }),

  // ── Analyses ──────────────────────────────────────────────────────────
  analyzeProduct: async (file: File): Promise<AnalysisResponse> => {
    const formData = new FormData();
    formData.append('files', file);
    formData.append('labels', JSON.stringify(['Front']));
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
      _timeout: 120000,
    } as any);
  },

  analyzeProducts: async (items: { file: File; label: string }[]): Promise<AnalysisResponse> => {
    const formData = new FormData();
    const labels: string[] = [];
    items.forEach((item) => {
      formData.append('files', item.file);
      labels.push(item.label || 'Front');
    });
    formData.append('labels', JSON.stringify(labels));
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
      _timeout: 120000,
    } as any);
  },

  analyzeText: (text: string): Promise<AnalysisResponse> =>
    fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  getDashboardStats: (): Promise<DashboardStats> => {
    return fetchJSON<DashboardStats>(`${BASE_URL}/stats`);
  },

  getTrends: (days = 14): Promise<TrendPoint[]> => {
    return fetchJSON<TrendPoint[]>(`${BASE_URL}/stats/trends?days=${days}`);
  },

  getStatusBreakdown: (): Promise<StatusBreakdown[]> => {
    return fetchJSON<StatusBreakdown[]>(`${BASE_URL}/stats/by-status`);
  },

  getHistory: (): Promise<HistoryItem[]> => {
    return fetchJSON<HistoryItem[]>(`${BASE_URL}/history`);
  },

  searchHistory: (q: string, status = 'ALL', limit = 50): Promise<{ items: HistoryItem[]; total: number }> => {
    const params = new URLSearchParams({ q, status, limit: String(limit) });
    return fetchJSON<{ items: HistoryItem[]; total: number }>(`${BASE_URL}/history/search?${params}`);
  },

  getAnalysis: (id: string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/history/${id}`);
  },

  deleteAnalysis: (id: string): Promise<{ message: string; id: string }> => {
    return fetchJSON<{ message: string; id: string }>(`${BASE_URL}/history/${id}`, {
      method: 'DELETE',
    });
  },

  clearHistory: (): Promise<{ message: string; deleted_count: number }> => {
    return fetchJSON<{ message: string; deleted_count: number }>(`${BASE_URL}/history`, {
      method: 'DELETE',
    });
  },

  // ── Enforcement (officer/admin only) ──────────────────────────────────
  estimatePenalty: (analysisId: string): Promise<PenaltyEstimate> => {
    return fetchJSON<PenaltyEstimate>(`${BASE_URL}/enforcement/penalty`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  showCauseNotice: (analysisId: string): Promise<ShowCauseNotice> => {
    return fetchJSON<ShowCauseNotice>(`${BASE_URL}/enforcement/notice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  // ── Demo / reference / misc ───────────────────────────────────────────
  getDemoCases: (): Promise<import('../types').DemoCaseMeta[]> => {
    return fetchJSON<import('../types').DemoCaseMeta[]>(`${BASE_URL}/demo/cases`);
  },

  getDemoCase: (caseNum: number | string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/demo/${caseNum}`);
  },

  getComplianceRules: (): Promise<ComplianceRule[]> => {
    return fetchJSON<ComplianceRule[]>(`${BASE_URL}/compliance/rules`);
  },

  getHealth: (): Promise<any> => {
    return fetchJSON<any>(`${BASE_URL}/health`);
  },
  getReportUrl: (id: string): string => `${BASE_URL}/report/${id}`,
  getCsvReportUrl: (id: string): string => `${BASE_URL}/report/${id}/csv`,
  getXlsxReportUrl: (id: string): string => `${BASE_URL}/report/${id}/xlsx`,
  getJsonReportUrl: (id: string): string => `${BASE_URL}/report/${id}/json`,
  getAssetUrl,
  extractText: (text: string): Promise<ProductInfo> =>
    fetchJSON<ProductInfo>(`${BASE_URL}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  checkCompliance: (info: ProductInfo): Promise<ComplianceResult> =>
    fetchJSON<ComplianceResult>(`${BASE_URL}/compliance/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(info),
    }),
};

export default api;