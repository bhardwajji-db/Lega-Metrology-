import { type AnalysisResponse, type DashboardStats, type HistoryItem, type ComplianceRule, type AuthUser, type TrendPoint, type StatusBreakdown, type PenaltyEstimate, type ShowCauseNotice, type ProductInfo, type ComplianceResult } from '../types';

export function getApiHost(): string {
  const custom = typeof window !== 'undefined' ? localStorage.getItem('metrcheck_api_url') : null;
  if (custom) return custom.replace(/\/$/, '');
  
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/$/, '');
  }

  // Auto-detect Capacitor (Android APK) or mobile native host
  if (typeof window !== 'undefined') {
    const isCapacitor = Boolean(
      (window as any).Capacitor?.isNativePlatform?.() ||
      window.location.protocol === 'capacitor:' ||
      (window.location.hostname === 'localhost' && window.navigator.userAgent.includes('Android'))
    );
    if (isCapacitor) {
      return 'http://192.168.60.183:8000';
    }
  }

  return '';
}

export function setApiHost(host: string): void {
  if (typeof window !== 'undefined') {
    const cleaned = (host || '').trim().replace(/\/$/, '');
    if (!cleaned) {
      localStorage.removeItem('metrcheck_api_url');
    } else {
      localStorage.setItem('metrcheck_api_url', cleaned);
    }
  }
}

export function getApiBaseUrl(): string {
  const host = getApiHost();
  return host ? `${host}/api` : '/api';
}

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

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> | undefined),
    ...authHeaders(),
  };

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (err: any) {
    const host = getApiHost();
    throw new Error(
      `Cannot connect to backend server${host ? ` (${host})` : ''}. Please ensure your laptop is running run.bat and connected to the same Wi-Fi!`
    );
  }

  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();

  let data: any = null;
  if (contentType.includes('application/json') || text.trim().startsWith('{') || text.trim().startsWith('[')) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const detail = data?.detail || (text.startsWith('<') ? `Backend unreachable (${response.status} ${response.statusText}). Check your server connection.` : text);
    if (response.status === 401) {
      if (!url.includes('/auth/login')) {
        tokenStore.clear();
      }
      throw new Error(detail || 'Authentication required. Please log in again.');
    }
    throw new Error(detail || `API error: ${response.status} ${response.statusText}`);
  }

  if (data === null) {
    const host = getApiHost();
    throw new Error(
      `Backend returned web page instead of data. Current server address: ${host || 'localhost:8000'}. Please tap 'Server Settings' to configure your connection.`
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

  adminDeleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/admin/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

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

  deleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

  // ── Analyses ──────────────────────────────────────────────────────────
  analyzeProduct: async (file: File): Promise<AnalysisResponse> => {
    const formData = new FormData();
    formData.append('files', file);
    formData.append('labels', JSON.stringify(['Front']));
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
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
    });
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
  getAssetUrl: (url: string): string => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) return url;
    const host = getApiHost();
    return host ? `${host}${url}` : url;
  },
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